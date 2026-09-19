"""Jarvis'ning o'z asboblari — Claude Agent SDK ichidagi MCP serveri sifatida.

Bu yerdagi asboblar Claude'ning tayyor asboblari (Read/Write/Bash/WebSearch)
ustiga qo'shiladi. To'rt guruh:

    xotira    — nimani bilaman (faktlar, oldingi suhbatlar)
    agenda    — nima qilish kerak (loyihalar, vazifalar, eslatmalar)
    aloqalar  — kim bilan bog'lanaman (Telegram, telefon)
    tizim     — macOS, Shortcuts, kanallar
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

from .. import notebook, selfwork
from ..brain.agenda import Agenda, format_when, parse_when
from ..brain.memory import Memory
from ..bus import EventBus
from . import channels, macos, media, telegram_user

log = logging.getLogger("jarvis.tools")

SERVER_NAME = "jarvis"

# Tashqi dunyoga ta'sir qilmaydigan asboblar — darvoza ularni tez o'tkazadi.
READ_ONLY = ToolAnnotations(readOnlyHint=True)

# Tasdiq so'ramasdan ishlatiladigan asboblar ro'yxati (`allowed_tools` uchun).
READ_ONLY_TOOLS = [
    "recall", "search_memory",
    "list_projects", "list_tasks", "daily_brief",
    "list_contacts", "find_contact",
    "telegram_chats", "telegram_read", "telegram_search", "telegram_overview",
    "telegram_folders", "telegram_members", "telegram_blocked",
    "telegram_contacts", "telegram_scheduled", "telegram_stories",
    "telegram_sessions", "telegram_admin_log", "telegram_gifts",
    "frontmost_app", "list_shortcuts",
    "self_issues", "self_status",
    "daftar_oqi", "daftarlar",
]


def _ok(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _fail(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


def _json(payload: Any) -> dict[str, Any]:
    return _ok(json.dumps(payload, ensure_ascii=False, indent=2))


def _memory_tools(memory: Memory) -> list[Any]:
    """Nimani bilaman."""

    @tool(
        "remember",
        "Foydalanuvchi haqidagi barqaror faktni xotiraga saqlaydi. Keyingi suhbatlarda "
        "ham eslab qolinadi. Masalan: kalit='ish_vaqti', qiymat='9:00 dan 18:00 gacha'.",
        {"kalit": str, "qiymat": str, "toifa": str},
    )
    async def remember(args: dict[str, Any]) -> dict[str, Any]:
        key = str(args.get("kalit", "")).strip()
        value = str(args.get("qiymat", "")).strip()
        if not key or not value:
            return _fail("`kalit` va `qiymat` bo'sh bo'lmasligi kerak")
        memory.remember(key, value, str(args.get("toifa") or "umumiy"))
        return _ok(f"Eslab qoldim: {key} = {value}")

    @tool("recall", "Xotiradan faktni kalit bo'yicha o'qiydi.", {"kalit": str},
          annotations=READ_ONLY)
    async def recall(args: dict[str, Any]) -> dict[str, Any]:
        value = memory.recall(str(args.get("kalit", "")))
        return _ok(value if value is not None else "Bunday fakt xotirada yo'q")

    @tool("forget", "Faktni xotiradan o'chiradi.", {"kalit": str})
    async def forget(args: dict[str, Any]) -> dict[str, Any]:
        key = str(args.get("kalit", ""))
        return _ok(f"O'chirildi: {key}" if memory.forget(key) else "Bunday fakt topilmadi")

    @tool(
        "search_memory",
        "Xotiradagi faktlar va oldingi suhbatlar ichidan matn bo'yicha qidiradi. "
        "«kechagi hisobotni yana yubor» kabi so'rovlarda ishlating.",
        {"soz": str},
        annotations=READ_ONLY,
    )
    async def search_memory(args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("soz", "")).strip()
        if not query:
            return _fail("Qidiruv so'zi bo'sh")
        facts = memory.search(query, limit=15)
        turns = memory.search_turns(query, limit=10)
        if not facts and not turns:
            return _ok("Hech narsa topilmadi")
        return _json({
            "faktlar": [{"kalit": f.key, "qiymat": f.value} for f in facts],
            "suhbatlar": turns,
        })

    return [remember, recall, forget, search_memory]


def _agenda_tools(agenda: Agenda, announce: Callable[[str], Any]) -> list[Any]:
    """Nima qilish kerak — loyihalar, vazifalar, eslatmalar."""

    @tool(
        "set_project",
        "Loyihani yaratadi yoki holatini yangilaydi. Faqat o'zgartirmoqchi bo'lgan "
        "maydonlarni bering. Holat: faol | kutilmoqda | tugagan | to'xtatilgan. "
        "Muddat formati: 2026-08-15 yoki 2026-08-15T18:00.",
        {"nom": str, "holat": str, "tavsif": str, "keyingi_qadam": str, "muddat": str},
    )
    async def set_project(args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("nom", "")).strip()
        if not name:
            return _fail("Loyiha nomi kerak")
        try:
            project = agenda.upsert_project(
                name,
                status=str(args["holat"]) if args.get("holat") else None,
                description=str(args["tavsif"]) if args.get("tavsif") else None,
                next_step=str(args["keyingi_qadam"]) if args.get("keyingi_qadam") else None,
                deadline=parse_when(args.get("muddat")),
            )
        except ValueError as exc:
            return _fail(str(exc))
        return _ok(f"Loyiha saqlandi: {project.name} ({project.status})")

    @tool(
        "list_projects",
        "Loyihalar ro'yxatini va ularning holatini beradi. «Loyihalarim qaysi "
        "bosqichda?» degan savolga shu bilan javob bering.",
        {"holat": str},
        annotations=READ_ONLY,
    )
    async def list_projects(args: dict[str, Any]) -> dict[str, Any]:
        projects = agenda.list_projects(str(args["holat"]) if args.get("holat") else None)
        if not projects:
            return _ok("Loyihalar yo'q")
        return _json([
            {
                "nom": p.name,
                "holat": p.status,
                "keyingi_qadam": p.next_step,
                "muddat": format_when(p.deadline),
                "tavsif": p.description,
            }
            for p in projects
        ])

    @tool(
        "add_task",
        "Vazifa qo'shadi. `vaqt` berilsa, Jarvis o'sha vaqtda o'zi eslatadi — "
        "foydalanuvchi so'ramasa ham. Format: 2026-08-09T10:00. "
        "Takror: kunlik | ish_kunlari | haftalik | oylik.",
        {"vazifa": str, "vaqt": str, "loyiha": str, "takror": str},
    )
    async def add_task(args: dict[str, Any]) -> dict[str, Any]:
        title = str(args.get("vazifa", "")).strip()
        if not title:
            return _fail("Vazifa matni kerak")
        try:
            task = agenda.add_task(
                title,
                project=str(args["loyiha"]) if args.get("loyiha") else None,
                remind_at=parse_when(args.get("vaqt")),
                repeat=str(args.get("takror") or ""),
            )
        except ValueError as exc:
            return _fail(str(exc))

        when = format_when(task.remind_at)
        return _ok(f"Qo'shildi (#{task.id}): {task.title}" + (f" — {when}" if when else ""))

    @tool(
        "list_tasks",
        "Bajarilmagan vazifalar ro'yxati. Loyiha nomi berilsa, faqat o'shanikilari.",
        {"loyiha": str},
        annotations=READ_ONLY,
    )
    async def list_tasks(args: dict[str, Any]) -> dict[str, Any]:
        tasks = agenda.list_tasks(project=str(args["loyiha"]) if args.get("loyiha") else None)
        if not tasks:
            return _ok("Bajarilmagan vazifa yo'q")
        return _json([
            {
                "id": t.id,
                "vazifa": t.title,
                "loyiha": t.project or "",
                "vaqt": format_when(t.remind_at),
                "takror": t.repeat,
            }
            for t in tasks
        ])

    @tool("complete_task", "Vazifani bajarilgan deb belgilaydi (id bo'yicha).", {"id": int})
    async def complete_task(args: dict[str, Any]) -> dict[str, Any]:
        task = agenda.complete_task(int(args.get("id", 0)))
        if task is None:
            return _fail("Bunday vazifa topilmadi")
        suffix = " Takrorlanuvchi — keyingisi rejaga qo'shildi." if task.repeat else ""
        return _ok(f"Bajarildi: {task.title}.{suffix}")

    @tool("delete_task", "Vazifani o'chiradi (id bo'yicha).", {"id": int})
    async def delete_task(args: dict[str, Any]) -> dict[str, Any]:
        ok = agenda.delete_task(int(args.get("id", 0)))
        return _ok("O'chirildi") if ok else _fail("Bunday vazifa topilmadi")

    @tool(
        "daily_brief",
        "Bugungi kun uchun qisqa xulosa: qanday ishlar bor, qaysi loyihalar faol.",
        {},
        annotations=READ_ONLY,
    )
    async def daily_brief(args: dict[str, Any]) -> dict[str, Any]:
        return _ok(agenda.daily_brief())

    @tool(
        "say_now",
        "Foydalanuvchiga darhol ovozli xabar aytadi. Uzoq ish tugaganda yoki "
        "muhim narsa yuz berganda ishlating — foydalanuvchi so'ramasa ham.",
        {"matn": str},
    )
    async def say_now(args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("matn", "")).strip()
        if not text:
            return _fail("Xabar matni kerak")
        await announce(text)
        return _ok("Aytildi")

    return [set_project, list_projects, add_task, list_tasks, complete_task,
            delete_task, daily_brief, say_now]


def _contact_tools(agenda: Agenda) -> list[Any]:
    """Kim bilan bog'lanaman."""

    @tool(
        "save_contact",
        "Aloqani saqlaydi: ism va Telegram chat ID (yoki @username) hamda telefon raqami. "
        "Shundan keyin «Alisherga yoz» deyish kifoya.",
        {"ism": str, "telegram": str, "telefon": str, "izoh": str},
    )
    async def save_contact(args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("ism", "")).strip()
        if not name:
            return _fail("Ism kerak")
        agenda.upsert_contact(
            name,
            telegram=str(args.get("telegram") or ""),
            phone=str(args.get("telefon") or ""),
            note=str(args.get("izoh") or ""),
        )
        return _ok(f"Aloqa saqlandi: {name}")

    @tool("list_contacts", "Saqlangan aloqalar ro'yxati.", {}, annotations=READ_ONLY)
    async def list_contacts(args: dict[str, Any]) -> dict[str, Any]:
        contacts = agenda.list_contacts()
        return _json(contacts) if contacts else _ok("Aloqalar yo'q")

    @tool(
        "find_contact",
        "Aloqani ism bo'yicha topadi. Xabar yuborishdan oldin shu bilan tekshiring.",
        {"ism": str},
        annotations=READ_ONLY,
    )
    async def find_contact(args: dict[str, Any]) -> dict[str, Any]:
        contact = agenda.find_contact(str(args.get("ism", "")))
        if contact is None:
            return _fail(
                "Bunday aloqa topilmadi yoki bir nechta mos keldi. "
                "`list_contacts` bilan ro'yxatni ko'ring."
            )
        return _json(contact)

    return [save_contact, list_contacts, find_contact]


def _system_tools(agenda: Agenda) -> list[Any]:
    """macOS, Shortcuts va tashqi kanallar."""

    @tool(
        "notify",
        "Ekranda macOS bildirishnomasini ko'rsatadi. Foydalanuvchi kompyuter oldida "
        "bo'lmasligi mumkin bo'lgan uzoq ishlarda foydali.",
        {"sarlavha": str, "matn": str},
    )
    async def notify(args: dict[str, Any]) -> dict[str, Any]:
        try:
            await macos.notify(str(args.get("sarlavha", "Jarvis")), str(args.get("matn", "")))
            return _ok("Bildirishnoma ko'rsatildi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool("open_app", "Kompyuterda ilovani ochadi. Masalan: 'Safari', 'Notes'.", {"nom": str})
    async def open_app(args: dict[str, Any]) -> dict[str, Any]:
        try:
            await macos.open_app(str(args.get("nom", "")))
            return _ok(f"{args.get('nom')} ochildi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool("open_url", "Havolani brauzerda ochadi.", {"havola": str})
    async def open_url(args: dict[str, Any]) -> dict[str, Any]:
        try:
            await macos.open_url(str(args.get("havola", "")))
            return _ok("Havola ochildi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool(
        "play_youtube",
        "YouTube'dan qo'shiq yoki videoni topib, brauzerda qo'yadi. "
        "`nima` — qo'shiq nomi va ijrochi. `sekund` berilsa, o'sha joydan boshlaydi. "
        "Masalan: nima='Roshka Ishondingmi', sekund=20.",
        {"nima": str, "sekund": int},
    )
    async def play_youtube(args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("nima", "")).strip()
        start = int(args.get("sekund") or 0)
        try:
            video_id, title = await media.find_video(query)
            await macos.open_url(media.watch_url(video_id, start))
        except (media.MediaError, macos.MacOsError) as exc:
            return _fail(str(exc))

        what = title or query
        when = f", {start}-sekunddan" if start else ""
        return _ok(f"Qo'yildi: {what}{when}")

    @tool("close_youtube", "YouTube ochilgan varaqlarni yopadi.", {})
    async def close_youtube(args: dict[str, Any]) -> dict[str, Any]:
        try:
            count = await media.close_youtube()
        except media.MediaError as exc:
            return _fail(str(exc))
        return _ok(f"{count} ta varaq yopildi" if count else "YouTube ochiq emas edi")

    @tool("playpause", "Ijroni to'xtatadi yoki davom ettiradi.", {})
    async def playpause(args: dict[str, Any]) -> dict[str, Any]:
        try:
            await media.playpause()
        except (media.MediaError, macos.MacOsError) as exc:
            return _fail(str(exc))
        return _ok("Bajarildi")

    @tool("frontmost_app", "Hozir qaysi ilova faol ekanini aytadi.", {}, annotations=READ_ONLY)
    async def frontmost_app(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await macos.frontmost_app())
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool(
        "send_message",
        "Messages ilovasi orqali SMS/iMessage yuboradi. `kimga` — saqlangan aloqa ismi, "
        "telefon raqami yoki Apple ID. Ism berilsa, aloqalardan raqami topiladi.",
        {"kimga": str, "matn": str},
    )
    async def send_message(args: dict[str, Any]) -> dict[str, Any]:
        target = str(args.get("kimga", "")).strip()
        text = str(args.get("matn", "")).strip()
        if not target or not text:
            return _fail("`kimga` va `matn` kerak")

        # Ism berilgan bo'lsa, aloqalardan raqamni topamiz.
        if not any(ch.isdigit() for ch in target) and "@" not in target:
            contact = agenda.find_contact(target)
            if contact is None or not contact["telefon"]:
                return _fail(
                    f"«{target}» uchun telefon raqami topilmadi. "
                    f"`save_contact` bilan saqlang yoki raqamni to'g'ridan-to'g'ri bering."
                )
            target = contact["telefon"]

        try:
            await macos.send_imessage(target, text)
            return _ok(f"Xabar yuborildi: {target}")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool(
        "send_telegram",
        "Telegram orqali xabar yuboradi. `kimga` bo'sh bo'lsa — foydalanuvchining "
        "o'ziga; ism berilsa — saqlangan aloqaga (uning nomidan yozadi).",
        {"matn": str, "kimga": str},
    )
    async def send_telegram(args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("matn", "")).strip()
        if not text:
            return _fail("Xabar matni kerak")

        chat_id = ""
        target = str(args.get("kimga") or "").strip()
        if target:
            contact = agenda.find_contact(target)
            if contact is None or not contact["telegram"]:
                return _fail(
                    f"«{target}» uchun Telegram manzili topilmadi. "
                    f"`save_contact` bilan saqlang."
                )
            chat_id = contact["telegram"]

        try:
            await channels.send_telegram(text, chat_id=chat_id)
            return _ok(f"Telegram'ga yuborildi{f' ({target})' if target else ''}")
        except channels.ChannelError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_chats",
        "Shaxsiy Telegram akkauntdagi oxirgi chatlar: kim yozgan, nechta o'qilmagan "
        "xabar bor. «Telegramda nima yangilik?» degan savolga shu bilan javob bering. "
        "`faqat_oqilmagan` = ha bo'lsa, faqat o'qilmaganlar ko'rsatiladi.",
        {"nechta": int, "faqat_oqilmagan": str},
        annotations=READ_ONLY,
    )
    async def telegram_chats(args: dict[str, Any]) -> dict[str, Any]:
        flag = str(args.get("faqat_oqilmagan") or "").strip().lower()
        unread = flag in ("ha", "yes", "true", "1")
        try:
            chats = await telegram_user.list_chats(
                limit=int(args.get("nechta") or 15), unread_only=unread
            )
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(chats) if chats else _ok("Yangi xabar yo'q")

    @tool(
        "telegram_read",
        "Bitta Telegram chatidagi oxirgi xabarlarni o'qiydi. `kim` — ism, @username "
        "yoki telefon raqam. Javob yozishdan oldin shu bilan kontekstni oling.",
        {"kim": str, "nechta": int},
        annotations=READ_ONLY,
    )
    async def telegram_read(args: dict[str, Any]) -> dict[str, Any]:
        try:
            chat = await telegram_user.read_chat(
                str(args.get("kim", "")), limit=int(args.get("nechta") or 15)
            )
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(chat)

    @tool(
        "telegram_send",
        "Telegramda **foydalanuvchining o'z nomidan** xabar yuboradi. `kimga` — ism, "
        "@username yoki telefon raqam. Matnni foydalanuvchi aytgandek yuboring; "
        "o'zingizdan qo'shimcha yozmang. Telegram ilovasi o'sha chatda ochiladi, "
        "ya'ni foydalanuvchi xabarni ko'rib turadi. Xato ketsa u aytadi — "
        "shunda `telegram_edit` yoki `telegram_undo` ni ishlating.",
        {"kimga": str, "matn": str},
    )
    async def telegram_send(args: dict[str, Any]) -> dict[str, Any]:
        target = str(args.get("kimga", "")).strip()
        text = str(args.get("matn", "")).strip()
        if not target or not text:
            return _fail("`kimga` va `matn` kerak")

        # Saqlangan aloqada @username bo'lsa, undan foydalanamiz — ism bo'yicha
        # qidirishdan ko'ra aniqroq.
        contact = agenda.find_contact(target) if not target.startswith(("@", "+")) else None
        if contact and contact.get("telegram"):
            target = contact["telegram"]

        try:
            name = await telegram_user.send_as_me(target, text)
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _ok(f"Yuborildi: {name}")

    @tool(
        "telegram_search",
        "Telegram yozishmalari ichidan matn bo'yicha qidiradi — sana va chat "
        "esda bo'lmasa ham topadi. `kim` berilsa faqat o'sha chatda qidiradi "
        "(saqlangan xabarlar uchun: kim='men'). «Asadga tashlagan edim», "
        "«saqlangan xabarlarimda bor edi» kabi so'rovlarda shuni ishlating.",
        {"soz": str, "kim": str, "nechta": int},
        annotations=READ_ONLY,
    )
    async def telegram_search(args: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await telegram_user.search(
                str(args.get("soz", "")),
                chat=str(args.get("kim") or ""),
                limit=int(args.get("nechta") or 20),
            )
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(result) if result["topildi"] else _ok("Hech narsa topilmadi")

    @tool(
        "telegram_overview",
        "Telegram akkauntining qisqa tahlili: nechta chat, qaysilari o'qilmagan, "
        "nechta guruh va kanal, qaysi kanallar uzoq vaqtdan beri jim. «Telegramni "
        "analiz qilib ber», «qaysi kanallar keraksiz?» degan so'rovlarda ishlating.",
        {"jim_kunlar": int},
        annotations=READ_ONLY,
    )
    async def telegram_overview(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _json(await telegram_user.overview(
                quiet_days=int(args.get("jim_kunlar") or 30)
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_send_file",
        "Telegramga fayl yuboradi: rasm, video, hujjat. `fayl` — kompyuterdagi "
        "to'liq yo'l (avval Glob/Bash bilan toping). `dumaloq_video` = ha bo'lsa "
        "dumaloq video sifatida yuboriladi (kvadrat, 60 soniyagacha mp4 kerak).",
        {"kimga": str, "fayl": str, "izoh": str, "dumaloq_video": str},
    )
    async def telegram_send_file(args: dict[str, Any]) -> dict[str, Any]:
        target = str(args.get("kimga", "")).strip()
        path = str(args.get("fayl", "")).strip()
        if not target or not path:
            return _fail("`kimga` va `fayl` kerak")

        round_video = str(args.get("dumaloq_video") or "").lower() in ("ha", "yes", "true", "1")
        try:
            name = await telegram_user.send_file(
                target, path, str(args.get("izoh") or ""), video_note=round_video
            )
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _ok(f"Yuborildi: {name}")

    @tool(
        "telegram_poll",
        "Guruh yoki kanalga so'rovnoma yuboradi. `variantlar` — javoblar, "
        "vergul bilan ajratilgan (kamida ikkita).",
        {"kimga": str, "savol": str, "variantlar": str, "kop_tanlov": str},
    )
    async def telegram_poll(args: dict[str, Any]) -> dict[str, Any]:
        options = [p.strip() for p in str(args.get("variantlar", "")).split(",") if p.strip()]
        multiple = str(args.get("kop_tanlov") or "").lower() in ("ha", "yes", "true", "1")
        try:
            name = await telegram_user.send_poll(
                str(args.get("kimga", "")), str(args.get("savol", "")), options, multiple
            )
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _ok(f"So'rovnoma yuborildi: {name}")

    @tool(
        "telegram_create",
        "Telegramda guruh yoki kanal yaratadi. `turi`: guruh | kanal. `azolar` — "
        "qo'shiladigan odamlar, vergul bilan (ixtiyoriy).",
        {"nom": str, "turi": str, "azolar": str, "tavsif": str},
    )
    async def telegram_create(args: dict[str, Any]) -> dict[str, Any]:
        members = [p.strip() for p in str(args.get("azolar") or "").split(",") if p.strip()]
        broadcast = str(args.get("turi") or "guruh").strip().lower() in ("kanal", "channel")
        try:
            return _ok(await telegram_user.create_group(
                str(args.get("nom", "")), members,
                about=str(args.get("tavsif") or ""), broadcast=broadcast,
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_add_members",
        "Guruh yoki kanalga odam qo'shadi. `kimlar` — vergul bilan ajratilgan "
        "ismlar yoki @username lar.",
        {"guruh": str, "kimlar": str},
    )
    async def telegram_add_members(args: dict[str, Any]) -> dict[str, Any]:
        members = [p.strip() for p in str(args.get("kimlar") or "").split(",") if p.strip()]
        try:
            return _ok(await telegram_user.add_members(str(args.get("guruh", "")), members))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_leave",
        "Guruh yoki kanaldan chiqadi. Chiqishdan oldin nomini aniq aytib bering — "
        "adashib boshqasidan chiqib ketmang.",
        {"kim": str},
    )
    async def telegram_leave(args: dict[str, Any]) -> dict[str, Any]:
        try:
            name = await telegram_user.leave(str(args.get("kim", "")))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _ok(f"Chiqildi: {name}")

    # --- Papkalar, huquqlar va chatni boshqarish ---
    #
    # Bular akkaunt orqali ishlaydigan qismning qolgan yarmi: papka yig'ish,
    # admin qilish, chiqarib yuborish, qo'shilish. Papkalar bot API'da umuman
    # yo'q, shuning uchun ularni faqat shu yerda qilish mumkin.

    @tool(
        "telegram_folders",
        "Telegram papkalari va ularning ichidagi chatlar ro'yxati.",
        {},
        annotations=READ_ONLY,
    )
    async def telegram_folders(args: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await telegram_user.folders()
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(rows) if rows else _ok("Papkalar yo'q")

    @tool(
        "telegram_folder",
        "Telegram papkasini yaratadi yoki tarkibini o'zgartiradi. `qoshish` va "
        "`olish` — vergul bilan ajratilgan kanal/guruh nomlari. Papka bo'lmasa "
        "o'zi yaratiladi. Masalan: nom='Ish', qoshish='Click Jobs, UzDev Jobs'.",
        {"nom": str, "qoshish": str, "olish": str},
    )
    async def telegram_folder(args: dict[str, Any]) -> dict[str, Any]:
        add = [p.strip() for p in str(args.get("qoshish") or "").split(",") if p.strip()]
        drop = [p.strip() for p in str(args.get("olish") or "").split(",") if p.strip()]
        try:
            return _ok(await telegram_user.folder_set(
                str(args.get("nom", "")), add=add, remove=drop,
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_folder_delete",
        "Telegram papkasini o'chiradi. Chatlarning o'zi joyida qoladi.",
        {"nom": str},
    )
    async def telegram_folder_delete(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.folder_delete(str(args.get("nom", ""))))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_members",
        "Guruh yoki kanal a'zolari ro'yxati.",
        {"guruh": str, "nechta": int, "qidiruv": str},
        annotations=READ_ONLY,
    )
    async def telegram_members(args: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await telegram_user.members(
                str(args.get("guruh", "")), limit=int(args.get("nechta") or 50),
                query=str(args.get("qidiruv") or ""),
            )
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(rows) if rows else _ok("A'zolar ko'rinmadi")

    @tool(
        "telegram_promote",
        "Odamni guruh yoki kanalda admin qiladi. `unvon` — admin yonida "
        "ko'rinadigan yozuv. `toliq` true bo'lsa, u boshqalarni ham admin qila oladi.",
        {"guruh": str, "kim": str, "unvon": str, "toliq": bool},
    )
    async def telegram_promote(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.promote(
                str(args.get("guruh", "")), str(args.get("kim", "")),
                rank=str(args.get("unvon") or ""), full=bool(args.get("toliq")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_demote",
        "Adminlikdan oladi. Guruhdan chiqarmaydi.",
        {"guruh": str, "kim": str},
    )
    async def telegram_demote(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.demote(
                str(args.get("guruh", "")), str(args.get("kim", "")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_kick",
        "Odamni guruh yoki kanaldan chiqarib yuboradi. `bloklansinmi` true "
        "bo'lsa, u qaytib kira olmaydi. Kimni chiqarayotganingizni aniq bilib turing.",
        {"guruh": str, "kim": str, "bloklansinmi": bool},
    )
    async def telegram_kick(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.kick(
                str(args.get("guruh", "")), str(args.get("kim", "")),
                ban=bool(args.get("bloklansinmi")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_unban",
        "Bloklangan odamni blokdan chiqaradi.",
        {"guruh": str, "kim": str},
    )
    async def telegram_unban(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.unban(
                str(args.get("guruh", "")), str(args.get("kim", "")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_join",
        "Kanal yoki guruhga qo'shiladi. @username yoki t.me havolasi "
        "(maxfiy taklifnoma ham bo'ladi).",
        {"qayerga": str},
    )
    async def telegram_join(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.join(str(args.get("qayerga", ""))))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_link",
        "Guruh yoki kanalning taklifnoma havolasini beradi. Odam qo'shib "
        "bo'lmaganda (maxfiylik sozlamasi) shuni yuboring.",
        {"guruh": str},
    )
    async def telegram_link(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.invite_link(str(args.get("guruh", ""))))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_rename",
        "Guruh yoki kanalning nomini yoki tavsifini o'zgartiradi.",
        {"guruh": str, "nom": str, "tavsif": str},
    )
    async def telegram_rename(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.rename(
                str(args.get("guruh", "")),
                title=str(args.get("nom") or ""), about=str(args.get("tavsif") or ""),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_pin",
        "Xabarni qadaydi yoki qadoqdan oladi. `id` — `telegram_read` ko'rsatgan raqam.",
        {"chat": str, "id": int, "olinsinmi": bool},
    )
    async def telegram_pin(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.pin(
                str(args.get("chat", "")), int(args.get("id") or 0),
                unpin=bool(args.get("olinsinmi")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_archive",
        "Chatni arxivga soladi yoki arxivdan oladi.",
        {"chat": str, "arxivgami": bool},
    )
    async def telegram_archive(args: dict[str, Any]) -> dict[str, Any]:
        wanted = args.get("arxivgami")
        try:
            return _ok(await telegram_user.archive(
                str(args.get("chat", "")), on=True if wanted is None else bool(wanted),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_mute",
        "Chat bildirishnomalarini o'chiradi yoki qaytaradi.",
        {"chat": str, "ochirilsinmi": bool},
    )
    async def telegram_mute(args: dict[str, Any]) -> dict[str, Any]:
        wanted = args.get("ochirilsinmi")
        try:
            return _ok(await telegram_user.mute(
                str(args.get("chat", "")), on=True if wanted is None else bool(wanted),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_forward",
        "Xabarlarni bir chatdan boshqasiga uzatadi. `idlar` — vergul bilan "
        "ajratilgan raqamlar (`telegram_read` ularni ko'rsatadi).",
        {"qayerdan": str, "idlar": str, "qayerga": str},
    )
    async def telegram_forward(args: dict[str, Any]) -> dict[str, Any]:
        ids = []
        for part in str(args.get("idlar") or "").split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        try:
            return _ok(await telegram_user.forward(
                str(args.get("qayerdan", "")), ids, str(args.get("qayerga", "")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_delete_messages",
        "Xabarlarni o'chiradi — qabul qiluvchida ham yo'qoladi. `idlar` — "
        "vergul bilan ajratilgan raqamlar.",
        {"chat": str, "idlar": str},
    )
    async def telegram_delete_messages(args: dict[str, Any]) -> dict[str, Any]:
        ids = []
        for part in str(args.get("idlar") or "").split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        try:
            return _ok(await telegram_user.delete_messages(str(args.get("chat", "")), ids))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_delete_chat",
        "Chatni o'chiradi. `hammadanmi` true bo'lsa — guruh/kanal BUTUNLAY "
        "o'chadi va qaytarib bo'lmaydi (faqat yaratuvchi qila oladi).",
        {"chat": str, "hammadanmi": bool},
    )
    async def telegram_delete_chat(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.delete_chat(
                str(args.get("chat", "")), everyone=bool(args.get("hammadanmi")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    # --- Odamlar, kontent va akkauntning o'zi ---

    @tool(
        "telegram_block",
        "Odamni bloklaydi. Guruhdan chiqarish emas — u sizga umuman yoza "
        "olmaydi. `ochirilsinmi` true bo'lsa, blokdan chiqaradi.",
        {"kim": str, "ochirilsinmi": bool},
    )
    async def telegram_block(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.block(
                str(args.get("kim", "")), unblock=bool(args.get("ochirilsinmi")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool("telegram_blocked", "Bloklanganlar ro'yxati.", {}, annotations=READ_ONLY)
    async def telegram_blocked(args: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await telegram_user.blocked_list()
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _ok("\n".join(rows) if rows else "Bloklangan odam yo'q")

    @tool(
        "telegram_contacts",
        "Telegram kontaktlari ro'yxati (Jarvisning o'z aloqalar daftari emas).",
        {"qidiruv": str},
        annotations=READ_ONLY,
    )
    async def telegram_contacts(args: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await telegram_user.contacts_list(str(args.get("qidiruv") or ""))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(rows) if rows else _ok("Kontakt topilmadi")

    @tool(
        "telegram_contact_add",
        "Telefon raqami bo'yicha Telegram kontakti qo'shadi.",
        {"telefon": str, "ism": str, "familiya": str},
    )
    async def telegram_contact_add(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.contact_add(
                str(args.get("telefon", "")), str(args.get("ism", "")),
                str(args.get("familiya") or ""),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool("telegram_contact_delete", "Telegram kontaktini o'chiradi.", {"kim": str})
    async def telegram_contact_delete(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.contact_delete(str(args.get("kim", ""))))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_react",
        "Xabarga reaksiya qo'yadi. `emoji` — masalan 👍 yoki ❤️. "
        "`olinsinmi` true bo'lsa, reaksiyani olib tashlaydi.",
        {"chat": str, "id": int, "emoji": str, "olinsinmi": bool},
    )
    async def telegram_react(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.react(
                str(args.get("chat", "")), int(args.get("id") or 0),
                emoji=str(args.get("emoji") or "👍"),
                remove=bool(args.get("olinsinmi")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool("telegram_mark_read", "Chatni o'qilgan deb belgilaydi.", {"chat": str})
    async def telegram_mark_read(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.mark_read(str(args.get("chat", ""))))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_gif",
        "GIF qidirib yuboradi. `nima` — qidiruv so'zi, masalan 'salom' yoki 'kulgu'.",
        {"kimga": str, "nima": str},
    )
    async def telegram_gif(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.send_gif(
                str(args.get("kimga", "")), str(args.get("nima") or ""),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_send_later",
        "Xabarni belgilangan vaqtda yuborishga qo'yadi — Telegram o'zi jo'natadi, "
        "kompyuter o'chiq bo'lsa ham. Vaqt: 2026-09-20T09:00.",
        {"kimga": str, "matn": str, "vaqt": str},
    )
    async def telegram_send_later(args: dict[str, Any]) -> dict[str, Any]:
        when = parse_when(args.get("vaqt"))
        if when is None:
            return _fail("Vaqtni tushunmadim. Masalan: 2026-09-20T09:00")
        try:
            return _ok(await telegram_user.send_later(
                str(args.get("kimga", "")), str(args.get("matn", "")), when,
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_scheduled", "Shu chat uchun rejalashtirilgan xabarlar.",
        {"chat": str}, annotations=READ_ONLY,
    )
    async def telegram_scheduled(args: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await telegram_user.scheduled(str(args.get("chat", "")))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(rows) if rows else _ok("Rejalashtirilgan xabar yo'q")

    # --- Storiyalar ---

    @tool(
        "telegram_story",
        "Storiya qo'yadi. `fayl` — rasm yoki video yo'li. `hammagami` false "
        "bo'lsa, faqat kontaktlarga ko'rinadi.",
        {"fayl": str, "izoh": str, "hammagami": bool},
    )
    async def telegram_story(args: dict[str, Any]) -> dict[str, Any]:
        everyone = args.get("hammagami")
        try:
            return _ok(await telegram_user.story_post(
                str(args.get("fayl", "")), caption=str(args.get("izoh") or ""),
                everyone=True if everyone is None else bool(everyone),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_stories", "Faol storiyalar (standart — o'zingizniki).",
        {"kim": str}, annotations=READ_ONLY,
    )
    async def telegram_stories(args: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await telegram_user.stories_of(str(args.get("kim") or "men"))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(rows) if rows else _ok("Faol storiya yo'q")

    @tool("telegram_story_delete", "O'z storiyangizni o'chiradi.", {"idlar": str})
    async def telegram_story_delete(args: dict[str, Any]) -> dict[str, Any]:
        ids = [int(p) for p in str(args.get("idlar") or "").split(",") if p.strip().isdigit()]
        try:
            return _ok(await telegram_user.story_delete(ids))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    # --- Ovozli chat va jonli efir ---

    @tool(
        "telegram_voice_chat",
        "Guruh yoki kanalda ovozli chat ochadi. `efirmi` true bo'lsa — jonli "
        "efir rejimi (video uzatish uchun). `yopilsinmi` true — ochiqni yopadi.",
        {"chat": str, "nom": str, "efirmi": bool, "yopilsinmi": bool},
    )
    async def telegram_voice_chat(args: dict[str, Any]) -> dict[str, Any]:
        chat = str(args.get("chat", ""))
        try:
            if bool(args.get("yopilsinmi")):
                return _ok(await telegram_user.voice_chat_stop(chat))
            return _ok(await telegram_user.voice_chat_start(
                chat, title=str(args.get("nom") or ""), rtmp=bool(args.get("efirmi")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_live_url",
        "Jonli efir uchun RTMP havolasi va kalitini beradi — OBS shularni "
        "so'raydi. `yangi_kalit` true bo'lsa, eski kalit bekor qilinadi.",
        {"chat": str, "yangi_kalit": bool},
    )
    async def telegram_live_url(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _json(await telegram_user.live_stream_url(
                str(args.get("chat", "")), new_key=bool(args.get("yangi_kalit")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    # --- Profil va akkaunt ---

    @tool(
        "telegram_profile",
        "Telegram profilini o'zgartiradi: ism, familiya, bio. Faqat "
        "berilgan maydonlar o'zgaradi.",
        {"ism": str, "familiya": str, "bio": str},
    )
    async def telegram_profile(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.profile_set(
                str(args.get("ism") or ""), str(args.get("familiya") or ""),
                str(args.get("bio") or ""),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool("telegram_username", "@username ni o'zgartiradi.", {"username": str})
    async def telegram_username(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.username_set(str(args.get("username", ""))))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool("telegram_photo", "Profil rasmini almashtiradi.", {"fayl": str})
    async def telegram_photo(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.profile_photo(str(args.get("fayl", ""))))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_sessions",
        "Akkauntga kirgan qurilmalar ro'yxati. Notanish qurilma ko'rinsa, "
        "`telegram_session_kill` bilan uzing.",
        {},
        annotations=READ_ONLY,
    )
    async def telegram_sessions(args: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await telegram_user.sessions()
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(rows)

    @tool("telegram_session_kill", "Boshqa qurilmadagi seansni uzadi.", {"hash": str})
    async def telegram_session_kill(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.session_kill(str(args.get("hash", ""))))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_privacy",
        "Maxfiylik sozlamasi. `nima`: oxirgi_korilgan | telefon | rasm | bio | "
        "uzatish | qongiroq | guruhga_qoshish | ovozli_xabar | yoshi. "
        "`kim`: hamma | kontaktlar | hech_kim.",
        {"nima": str, "kim": str},
    )
    async def telegram_privacy(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.privacy_set(
                str(args.get("nima", "")), str(args.get("kim") or "hamma"),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    # --- Guruh sozlamalari ---

    @tool(
        "telegram_slow_mode",
        "Sekin rejim: a'zolar shuncha soniyada bir marta yoza oladi. 0 — o'chirish.",
        {"guruh": str, "soniya": int},
    )
    async def telegram_slow_mode(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.slow_mode(
                str(args.get("guruh", "")), int(args.get("soniya") or 0),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_permissions",
        "Guruhdagi oddiy a'zolar nima qila olishini belgilaydi.",
        {"guruh": str, "yozsinmi": bool, "media_yuborsinmi": bool, "odam_qoshsinmi": bool},
    )
    async def telegram_permissions(args: dict[str, Any]) -> dict[str, Any]:
        def flag(key: str) -> bool:
            value = args.get(key)
            return True if value is None else bool(value)

        try:
            return _ok(await telegram_user.chat_permissions(
                str(args.get("guruh", "")),
                can_write=flag("yozsinmi"), can_media=flag("media_yuborsinmi"),
                can_invite=flag("odam_qoshsinmi"),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_admin_log", "Guruhda kim nima qilgani (adminlar jurnali).",
        {"guruh": str, "nechta": int}, annotations=READ_ONLY,
    )
    async def telegram_admin_log(args: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await telegram_user.admin_log(
                str(args.get("guruh", "")), limit=int(args.get("nechta") or 20),
            )
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(rows) if rows else _ok("Jurnal bo'sh")

    # --- Sovg'alar ---

    @tool(
        "telegram_voice_search",
        "OVOZLI xabarlar ichidan so'z qidiradi. Telegramning o'z qidiruvi buni "
        "qila olmaydi — ovozli xabarda matn yo'q, shuning uchun avval matnga "
        "aylantiriladi. «Ovozlida aytgan edim», «gapirganda aytgandi» degan "
        "so'rovlarda AYNAN shuni ishlating, `telegram_search` ni emas. "
        "Birinchi marta sekin (har bir yozuv aylantiriladi), keyin tez.",
        {"chat": str, "soz": str, "nechta": int},
    )
    async def telegram_voice_search(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _json(await telegram_user.voice_search(
                str(args.get("chat", "")), str(args.get("soz", "")),
                limit=int(args.get("nechta") or 60),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_voice_read",
        "Chatdagi ovozli xabarlarni matnga aylantirib beradi (yangisidan "
        "eskisiga). «Ovozlilarni o'qib ber», «nima deganini ayt» degan "
        "so'rovlar uchun.",
        {"chat": str, "nechta": int},
    )
    async def telegram_voice_read(args: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await telegram_user.voice_transcripts(
                str(args.get("chat", "")), limit=int(args.get("nechta") or 20),
            )
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(rows) if rows else _ok("Ovozli xabar topilmadi")

    @tool(
        "telegram_export",
        "BUTUN suhbatni matn faylga yozadi — ovozli xabarlar va doira-videolar "
        "ham matnga aylantirilib, o'z o'rniga qo'yiladi. Kelishmovchilikda "
        "(«aytdim / aytmadim», «berdim / bermadim») dalil sifatida ishlatiladi: "
        "natija faylda qoladi, uni saqlash va ko'rsatish mumkin. Uzoq ish — "
        "foydalanuvchini oldindan ogohlantiring.",
        {"chat": str, "nechta": int, "ovozli_ham": bool},
    )
    async def telegram_export(args: dict[str, Any]) -> dict[str, Any]:
        voice = args.get("ovozli_ham")
        try:
            return _json(await telegram_user.export_chat(
                str(args.get("chat", "")), limit=int(args.get("nechta") or 1000),
                voice=True if voice is None else bool(voice),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_gifts",
        "Hisobingizdagi sovg'alar: qaysi biri NFT, o'tkazsa bo'ladimi va "
        "qancha Stars turadi.",
        {},
        annotations=READ_ONLY,
    )
    async def telegram_gifts(args: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await telegram_user.gifts()
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _json(rows) if rows else _ok("Sovg'a yo'q")

    @tool(
        "telegram_gift_transfer",
        "NFT sovg'ani boshqa odamga o'tkazadi. Faqat unique (NFT) sovg'alar "
        "o'tadi, Stars talab qilishi mumkin va QAYTARIB BO'LMAYDI. "
        "O'tkazishdan oldin `telegram_gifts` bilan aniq nomini tekshiring.",
        {"sovga": str, "kimga": str},
    )
    async def telegram_gift_transfer(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await telegram_user.gift_transfer(
                str(args.get("sovga", "")), str(args.get("kimga", "")),
            ))
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))

    @tool(
        "telegram_edit",
        "Telegramda oxirgi yuborilgan xabarni tuzatadi. Foydalanuvchi «unday emas», "
        "«tahrirla», «o'zgartir» desa shuni ishlating. `matn` — xabarning to'liq "
        "yangi matni (qo'shimcha emas, o'rniga yoziladi).",
        {"matn": str},
    )
    async def telegram_edit(args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("matn", "")).strip()
        if not text:
            return _fail("Yangi matn kerak")
        try:
            name = await telegram_user.edit_last(text)
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _ok(f"Tuzatildi: {name}")

    @tool(
        "telegram_undo",
        "Telegramda oxirgi yuborilgan xabarni olib tashlaydi — qabul qiluvchida ham "
        "yo'qoladi. Foydalanuvchi «o'chir», «bekor qil», «yuborma edi» desa shuni "
        "ishlating.",
        {},
    )
    async def telegram_undo(args: dict[str, Any]) -> dict[str, Any]:
        try:
            name = await telegram_user.undo_last()
        except telegram_user.TelegramUserError as exc:
            return _fail(str(exc))
        return _ok(f"Olib tashlandi: {name}")

    @tool(
        "list_shortcuts",
        "Mavjud macOS Shortcuts qisqa yo'llari ro'yxati. Telefonda amal bajarish "
        "uchun avval shu ro'yxatdan mos qisqa yo'lni toping.",
        {},
        annotations=READ_ONLY,
    )
    async def list_shortcuts(args: dict[str, Any]) -> dict[str, Any]:
        try:
            names = await macos.list_shortcuts()
            return _ok("\n".join(names) if names else "Qisqa yo'llar topilmadi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool(
        "run_shortcut",
        "macOS Shortcuts qisqa yo'lini ishga tushiradi. iCloud orqali sinxronlangan "
        "qisqa yo'llar telefonda ham amal bajarishi mumkin.",
        {"nom": str, "kirish": str},
    )
    async def run_shortcut(args: dict[str, Any]) -> dict[str, Any]:
        try:
            output = await macos.run_shortcut(
                str(args.get("nom", "")), str(args.get("kirish") or "")
            )
            return _ok(output or "Qisqa yo'l bajarildi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool(
        "call_n8n",
        "n8n webhook'ini chaqiradi va javobini qaytaradi — mavjud avtomatlashtirish "
        "jarayonlarini ishga tushirish uchun.",
        {"malumot": str},
    )
    async def call_n8n(args: dict[str, Any]) -> dict[str, Any]:
        raw = str(args.get("malumot", "{}"))
        try:
            payload = json.loads(raw) if raw.strip().startswith("{") else {"text": raw}
        except json.JSONDecodeError:
            payload = {"text": raw}
        try:
            return _ok(await channels.call_n8n(payload))
        except channels.ChannelError as exc:
            return _fail(str(exc))

    return [notify, open_app, open_url, play_youtube, close_youtube, playpause,
            frontmost_app, send_message, send_telegram,
            telegram_chats, telegram_read, telegram_search, telegram_overview,
            telegram_send, telegram_send_file, telegram_poll,
            telegram_create, telegram_add_members, telegram_leave,
            telegram_edit, telegram_undo,
            telegram_folders, telegram_folder, telegram_folder_delete,
            telegram_members, telegram_promote, telegram_demote,
            telegram_kick, telegram_unban, telegram_join, telegram_link,
            telegram_rename, telegram_pin, telegram_archive, telegram_mute,
            telegram_forward, telegram_delete_messages, telegram_delete_chat,
            telegram_block, telegram_blocked, telegram_contacts,
            telegram_contact_add, telegram_contact_delete,
            telegram_react, telegram_mark_read, telegram_gif,
            telegram_send_later, telegram_scheduled,
            telegram_story, telegram_stories, telegram_story_delete,
            telegram_voice_chat, telegram_live_url,
            telegram_profile, telegram_username, telegram_photo,
            telegram_sessions, telegram_session_kill, telegram_privacy,
            telegram_slow_mode, telegram_permissions, telegram_admin_log,
            telegram_gifts, telegram_gift_transfer,
            telegram_voice_search, telegram_voice_read, telegram_export,
            list_shortcuts, run_shortcut, call_n8n]


def _self_tools(bus: EventBus, memory: Memory) -> list[Any]:
    """O'z ustida ishlash — Jarvisning o'z kodini o'zgartirishi.

    Tartib ataylab qat'iy: `self_start` → tahrir → `self_check` → `self_finish`
    → (kerak bo'lsa) `self_restart`. Sababi — `self_start` ikkita ishni qiladi:
    ekranda «band» yozuvini yoqadi (foydalanuvchi bekorga gapirmasin) va
    git'da orqaga qaytish nuqtasini qoldiradi.
    """

    @tool(
        "self_status",
        "O'z kodining holati: qaysi shoxda, qaysi fayllar o'zgargan. "
        "O'zgartirishni boshlashdan oldin shuni ko'ring.",
        {},
        annotations=READ_ONLY,
    )
    async def self_status(args: dict[str, Any]) -> dict[str, Any]:
        return _ok(await selfwork.git_status())

    @tool(
        "self_issues",
        "Kamchiliklar daftari: foydalanuvchi shikoyat qilgan va Jarvis o'zi "
        "sezgan muammolar. Bo'sh vaqt bo'lganda shu ro'yxatdan ish oling.",
        {"nechta": int},
        annotations=READ_ONLY,
    )
    async def self_issues(args: dict[str, Any]) -> dict[str, Any]:
        rows = selfwork.open_issues(limit=int(args.get("nechta") or 20))
        return _json(rows) if rows else _ok("Ochiq kamchilik yo'q")

    @tool(
        "self_note",
        "Kamchilikni daftarga yozadi. Foydalanuvchi Jarvisning ishidan norozi "
        "bo'lsa («bu yoqmadi», «sekin», «noto'g'ri tushunding») — darhol shu "
        "asbob bilan yozib qo'ying, hatto darhol tuzatmasangiz ham.",
        {"kamchilik": str, "izoh": str},
    )
    async def self_note(args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("kamchilik", "")).strip()
        if not text:
            return _fail("Kamchilik matni kerak")
        selfwork.note("shikoyat", text, str(args.get("izoh") or ""))
        return _ok("Yozib qo'ydim")

    @tool(
        "self_start",
        "O'z kodini o'zgartirishni boshlaydi: ekranda «o'z ustida ishlamoqda» "
        "yozuvi paydo bo'ladi va git'da orqaga qaytish nuqtasi saqlanadi. "
        "Kodni tahrirlashdan OLDIN chaqiring.",
        {"nima": str},
    )
    async def self_start(args: dict[str, Any]) -> dict[str, Any]:
        what = str(args.get("nima", "")).strip() or "o'z kodini yaxshilash"
        await bus.work(f"O'z ustida ishlamoqda — {what}")
        saved = await selfwork.snapshot(what)
        return _ok(
            f"Boshlandi. {saved}. Endi `{selfwork.REPO_ROOT}` ichidagi fayllarni "
            f"tahrirlang, so'ng `self_check` bilan tekshiring."
        )

    @tool(
        "self_check",
        "O'zgartirilgan kodni tekshiradi: testlar va linter. Qayta ishga "
        "tushirishdan oldin MAJBURIY — buzuq kod bilan qayta ishga tushish "
        "Jarvisni butunlay to'xtatib qo'yadi.",
        {},
    )
    async def self_check(args: dict[str, Any]) -> dict[str, Any]:
        ok, report = await selfwork.run_checks()
        return _ok(("Hammasi joyida.\n" if ok else "Muammo bor.\n") + report)

    @tool(
        "self_finish",
        "O'z ustida ishlashni tugatadi: ekrandagi «band» yozuvi o'chadi. "
        "`kamchilik` berilsa, daftardagi o'sha yozuv yopiladi.",
        {"natija": str, "kamchilik": str},
    )
    async def self_finish(args: dict[str, Any]) -> dict[str, Any]:
        await bus.work("")
        result = str(args.get("natija") or "").strip()
        issue = str(args.get("kamchilik") or "").strip()
        if issue:
            selfwork.close_issue(issue)
        if result:
            memory.remember(f"ozgarish_{selfwork.stamp()}", result[:400], "o'zgarishlar")
        return _ok("Tugadi")

    @tool(
        "self_restart",
        "Jarvisni qayta ishga tushiradi — o'zgartirilgan kod shundan keyin "
        "kuchga kiradi. Avval `self_check` dan o'ting.",
        {"sabab": str},
    )
    async def self_restart(args: dict[str, Any]) -> dict[str, Any]:
        reason = str(args.get("sabab") or "yangi kod")
        await bus.work("Qayta ishga tushmoqda")
        selfwork.note("bajarildi", f"qayta ishga tushdi: {reason}")
        selfwork.schedule_restart(3.0)
        return _ok("Qayta ishga tushyapman — bir necha soniyadan keyin qaytaman")

    @tool(
        "self_revert",
        "Saqlanmagan barcha o'zgarishlarni bekor qiladi — «orqaga qaytar». "
        "Yangi xatti-harakat yoqmasa yoki nimadir buzilsa ishlating.",
        {},
    )
    async def self_revert(args: dict[str, Any]) -> dict[str, Any]:
        return _ok(await selfwork.revert())

    return [self_status, self_issues, self_note, self_start, self_check,
            self_finish, self_restart, self_revert]


def _notebook_tools() -> list[Any]:
    """Daftarlar — Jarvis o'zi yozib boradigan matn fayllari.

    Xotiradagi kalit/qiymat juftliklaridan farqi: bular oddiy Markdown
    fayllar, `~/.jarvis/` da. Foydalanuvchi ularni ochib o'qishi, tahrirlashi
    va o'chirishi mumkin — «nima eslab qolgansan?» degan savolga javob
    ko'rinadigan bo'lsin.
    """

    @tool(
        "daftarlar",
        "Daftarlar ro'yxati va har birida nechta yozuv borligi: men (foydalanuvchi "
        "haqida), qoidalar, xatolar, lugat.",
        {},
        annotations=READ_ONLY,
    )
    async def daftarlar(args: dict[str, Any]) -> dict[str, Any]:
        return _json(notebook.summary())

    @tool(
        "daftar_oqi",
        "Daftarni o'qiydi. `daftar`: men | qoidalar | xatolar | lugat.",
        {"daftar": str},
        annotations=READ_ONLY,
    )
    async def daftar_oqi(args: dict[str, Any]) -> dict[str, Any]:
        note = notebook.resolve(str(args.get("daftar", "")))
        if note is None:
            return _fail("Daftar nomi: men | qoidalar | xatolar | lugat")
        rows = notebook.entries(note)
        return _json(rows) if rows else _ok(f"«{note.title}» hozircha bo'sh")

    @tool(
        "eslab_qol",
        "Daftarga yozadi — bu ESLAB QOLISH asbobi. Qaysi daftarga:\n"
        "  men      — foydalanuvchi haqidagi fakt, odat, afzallik, gapirish uslubi\n"
        "  qoidalar — «bundan keyin shunday qil» / «bunday qilma» ko'rsatmasi\n"
        "  xatolar  — qilgan xatoing va uni takrorlamaslik uchun xulosa\n"
        "  lugat    — foydalanuvchi tushunmagan so'z va uning ma'nosi\n"
        "Foydalanuvchi «buni eslab qol» desa, MAJBURIY chaqiring.",
        {"daftar": str, "yozuv": str},
    )
    async def eslab_qol(args: dict[str, Any]) -> dict[str, Any]:
        note = notebook.resolve(str(args.get("daftar", "")))
        if note is None:
            return _fail("Daftar nomi: men | qoidalar | xatolar | lugat")
        text = str(args.get("yozuv", "")).strip()
        if not text:
            return _fail("Nimani eslab qolishni ayting")
        return _ok(notebook.add(note, text))

    @tool(
        "esdan_chiqar",
        "Daftardagi yozuvni o'chiradi. Foydalanuvchi «bu noto'g'ri», «buni "
        "o'chir», «endi bunday emas» desa ishlating.",
        {"daftar": str, "yozuv": str},
    )
    async def esdan_chiqar(args: dict[str, Any]) -> dict[str, Any]:
        note = notebook.resolve(str(args.get("daftar", "")))
        if note is None:
            return _fail("Daftar nomi: men | qoidalar | xatolar | lugat")
        return _ok(notebook.remove(note, str(args.get("yozuv", ""))))

    return [daftarlar, daftar_oqi, eslab_qol, esdan_chiqar]


def build_server(
    memory: Memory, agenda: Agenda, announce: Callable[[str], Any], bus: EventBus
) -> Any:
    """MCP serverini yaratadi.

    `announce` — Jarvis'ga darhol gapirish imkonini beruvchi qayta chaqiruv
    (asinxron). Uni yadro beradi, chunki ovoz chiqarish yadroga tegishli.
    """
    tools = [
        *_memory_tools(memory),
        *_agenda_tools(agenda, announce),
        *_contact_tools(agenda),
        *_system_tools(agenda),
        *_self_tools(bus, memory),
        *_notebook_tools(),
    ]
    return create_sdk_mcp_server(name=SERVER_NAME, version="0.3.0", tools=tools)


def read_only_tool_names() -> list[str]:
    """Tasdiq so'ramasdan ishlatsa bo'ladigan asboblarning to'liq nomlari."""
    return [f"mcp__{SERVER_NAME}__{name}" for name in READ_ONLY_TOOLS]
