"""Jarvis'ning o'z asboblari — Claude Agent SDK ichidagi MCP serveri sifatida.

Bu yerdagi asboblar Claude'ning tayyor asboblari (Read/Write/Bash/WebSearch)
ustiga qo'shiladi. To'rt guruh:

    xotira    — nimani bilaman (faktlar, oldingi suhbatlar)
    agenda    — nima qilish kerak (loyihalar, vazifalar, eslatmalar)
    aloqalar  — kim bilan bog'lanaman (Telegram, telefon)
    tizim     — macOS, Shortcuts, kanallar
    telegram  — Telegram hisobini to'liq boshqarish (kanal, guruh, papka, a'zolar)
    o'zi      — o'z kodini o'zgartirish, tekshirish, qayta ishga tushish
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

from .. import selfwork
from ..brain.agenda import Agenda, format_when, parse_when
from ..brain.memory import Memory
from ..bus import EventBus
from . import channels, macos, media
from . import telegram as tg

log = logging.getLogger("jarvis.tools")

SERVER_NAME = "jarvis"

# Tashqi dunyoga ta'sir qilmaydigan asboblar — darvoza ularni tez o'tkazadi.
READ_ONLY = ToolAnnotations(readOnlyHint=True)

# Tasdiq so'ramasdan ishlatiladigan asboblar ro'yxati (`allowed_tools` uchun).
READ_ONLY_TOOLS = [
    "recall", "search_memory",
    "list_projects", "list_tasks", "daily_brief",
    "list_contacts", "find_contact",
    "frontmost_app", "list_shortcuts",
    "tg_me", "tg_chats", "tg_read", "tg_search", "tg_members", "tg_folders",
    "self_issues", "self_status",
]


def _list_arg(value: Any) -> list[str]:
    """«a, b, c» ko'rinishidagi qiymatni ro'yxatga aylantiradi.

    Asbob sxemasida ro'yxat turini ishlatmaymiz: model ba'zan JSON massiv,
    ba'zan oddiy vergul bilan ajratilgan satr yuboradi. Ikkalasini ham
    qabul qilish — bitta formatni talab qilib, qolganida yiqilishdan afzal.
    """
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in text.split(",") if part.strip()]


def _int_list_arg(value: Any) -> list[int]:
    out: list[int] = []
    for part in _list_arg(value):
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out


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
            list_shortcuts, run_shortcut, call_n8n]


def _telegram_tools() -> list[Any]:
    """Telegram — foydalanuvchining o'z hisobi orqali to'liq boshqaruv.

    Bu yerdagi asboblar `channels.send_telegram` (bot) dan tubdan farq qiladi:
    bot faqat sizga xabar yuboradi, bular esa siz qila oladigan hamma ishni
    qiladi — kanal ochish, odam qo'shish, admin qilish, papka yig'ish.
    """

    async def _text(coro: Any) -> dict[str, Any]:
        """Natijasi bitta gap bo'lgan amallar uchun umumiy xato ushlagich."""
        try:
            return _ok(str(await coro))
        except tg.TelegramError as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.exception("Telegram amali yiqildi")
            return _fail(f"Telegram xatosi: {exc}")

    async def _data(coro: Any) -> dict[str, Any]:
        """Natijasi ro'yxat/jadval bo'lgan amallar uchun."""
        try:
            payload = await coro
        except tg.TelegramError as exc:
            return _fail(str(exc))
        except Exception as exc:
            log.exception("Telegram so'rovi yiqildi")
            return _fail(f"Telegram xatosi: {exc}")
        if not payload:
            return _ok("Hech nima topilmadi")
        return _json(payload)

    # --- o'qish ---

    @tool("tg_me", "Telegram'da qaysi hisob ulanganini aytadi.", {}, annotations=READ_ONLY)
    async def tg_me(args: dict[str, Any]) -> dict[str, Any]:
        return await _data(tg.me())

    @tool(
        "tg_chats",
        "Telegram suhbatlari ro'yxati. `qidiruv` — nom bo'yicha filtr, "
        "`turi` — kanal | guruh | shaxs | bot. Kanal nomini aniqlashtirish "
        "kerak bo'lganda birinchi shu asbobni ishlating.",
        {"qidiruv": str, "turi": str, "nechta": int},
        annotations=READ_ONLY,
    )
    async def tg_chats(args: dict[str, Any]) -> dict[str, Any]:
        return await _data(tg.chats(
            query=str(args.get("qidiruv") or ""),
            kind=str(args.get("turi") or ""),
            limit=int(args.get("nechta") or 60),
        ))

    @tool(
        "tg_read",
        "Kanal yoki suhbatdagi oxirgi xabarlarni o'qiydi. Kanallarni ko'rib "
        "chiqish, e'lonlarni saralash uchun shu ishlatiladi.",
        {"qayerdan": str, "nechta": int},
        annotations=READ_ONLY,
    )
    async def tg_read(args: dict[str, Any]) -> dict[str, Any]:
        target = str(args.get("qayerdan", "")).strip()
        if not target:
            return _fail("`qayerdan` kerak — kanal nomi yoki @username")
        return await _data(tg.history(target, limit=int(args.get("nechta") or 20)))

    @tool(
        "tg_search",
        "Telegram xabarlari ichidan qidiradi. `qayerda` bo'sh bo'lsa — "
        "barcha suhbatlardan.",
        {"soz": str, "qayerda": str, "nechta": int},
        annotations=READ_ONLY,
    )
    async def tg_search(args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("soz", "")).strip()
        if not query:
            return _fail("Qidiruv so'zi kerak")
        return await _data(tg.search(
            query, target=str(args.get("qayerda") or ""),
            limit=int(args.get("nechta") or 20),
        ))

    @tool(
        "tg_members", "Guruh yoki kanal a'zolari ro'yxati.",
        {"qayerda": str, "nechta": int, "qidiruv": str}, annotations=READ_ONLY,
    )
    async def tg_members(args: dict[str, Any]) -> dict[str, Any]:
        return await _data(tg.members(
            str(args.get("qayerda", "")), limit=int(args.get("nechta") or 50),
            query=str(args.get("qidiruv") or ""),
        ))

    @tool(
        "tg_folders", "Telegram papkalari va ularning ichidagi suhbatlar.",
        {}, annotations=READ_ONLY,
    )
    async def tg_folders(args: dict[str, Any]) -> dict[str, Any]:
        return await _data(tg.folders())

    # --- yozish ---

    @tool(
        "tg_send",
        "Telegram orqali SIZNING nomingizdan xabar yuboradi. `kimga` — "
        "kanal/guruh nomi, @username yoki «men» (saqlangan xabarlar).",
        {"kimga": str, "matn": str},
    )
    async def tg_send(args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("matn", "")).strip()
        if not text:
            return _fail("Xabar matni kerak")
        return await _text(tg.send(str(args.get("kimga") or "men"), text))

    @tool(
        "tg_forward",
        "Xabarlarni bir suhbatdan boshqasiga uzatadi. `idlar` — vergul bilan.",
        {"qayerdan": str, "idlar": str, "qayerga": str},
    )
    async def tg_forward(args: dict[str, Any]) -> dict[str, Any]:
        ids = _int_list_arg(args.get("idlar"))
        if not ids:
            return _fail("Xabar id lari kerak — `tg_read` ularni ko'rsatadi")
        return await _text(tg.forward(
            str(args.get("qayerdan", "")), ids, str(args.get("qayerga", "")),
        ))

    @tool(
        "tg_create",
        "Yangi kanal yoki guruh ochadi. `kanalmi` true bo'lsa — kanal (faqat "
        "siz yozasiz), false bo'lsa — guruh. `azolar` — vergul bilan ajratilgan "
        "ismlar yoki @username lar.",
        {"nom": str, "tavsif": str, "kanalmi": bool, "azolar": str},
    )
    async def tg_create(args: dict[str, Any]) -> dict[str, Any]:
        title = str(args.get("nom", "")).strip()
        if not title:
            return _fail("Nom kerak")
        return await _data(tg.create_chat(
            title,
            about=str(args.get("tavsif") or ""),
            broadcast=bool(args.get("kanalmi")),
            members_=_list_arg(args.get("azolar")),
        ))

    @tool(
        "tg_invite", "Guruh yoki kanalga odam qo'shadi. `kimlar` — vergul bilan.",
        {"qayerga": str, "kimlar": str},
    )
    async def tg_invite(args: dict[str, Any]) -> dict[str, Any]:
        users = _list_arg(args.get("kimlar"))
        if not users:
            return _fail("Kimni qo'shish kerakligini ayting")
        return await _text(tg.invite(str(args.get("qayerga", "")), users))

    @tool(
        "tg_promote",
        "Odamni admin qiladi. `unvon` — admin yonida ko'rinadigan yozuv. "
        "`toliq` true bo'lsa, u boshqalarni ham admin qila oladi.",
        {"qayerda": str, "kim": str, "unvon": str, "toliq": bool},
    )
    async def tg_promote(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.promote(
            str(args.get("qayerda", "")), str(args.get("kim", "")),
            rank=str(args.get("unvon") or ""), full=bool(args.get("toliq")),
        ))

    @tool("tg_demote", "Adminlikdan oladi (guruhdan chiqarmaydi).",
          {"qayerda": str, "kim": str})
    async def tg_demote(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.demote(str(args.get("qayerda", "")), str(args.get("kim", ""))))

    @tool(
        "tg_kick",
        "Odamni guruh yoki kanaldan chiqarib yuboradi. `bloklansinmi` true "
        "bo'lsa, u qaytib kira olmaydi.",
        {"qayerdan": str, "kim": str, "bloklansinmi": bool},
    )
    async def tg_kick(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.kick(
            str(args.get("qayerdan", "")), str(args.get("kim", "")),
            ban=bool(args.get("bloklansinmi")),
        ))

    @tool("tg_unban", "Bloklangan odamni blokdan chiqaradi.",
          {"qayerda": str, "kim": str})
    async def tg_unban(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.unban(str(args.get("qayerda", "")), str(args.get("kim", ""))))

    @tool(
        "tg_join",
        "Kanal yoki guruhga qo'shiladi. @username yoki t.me havolasi "
        "(maxfiy taklifnoma ham bo'ladi).",
        {"qayerga": str},
    )
    async def tg_join(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.join(str(args.get("qayerga", ""))))

    @tool("tg_leave", "Kanal yoki guruhdan chiqadi.", {"qayerdan": str})
    async def tg_leave(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.leave(str(args.get("qayerdan", ""))))

    @tool("tg_rename", "Kanal/guruh nomini yoki tavsifini o'zgartiradi.",
          {"qayerda": str, "nom": str, "tavsif": str})
    async def tg_rename(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.rename(
            str(args.get("qayerda", "")),
            title=str(args.get("nom") or ""), about=str(args.get("tavsif") or ""),
        ))

    @tool("tg_link", "Kanal/guruhning taklifnoma havolasini beradi.", {"qayerda": str})
    async def tg_link(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.invite_link(str(args.get("qayerda", ""))))

    @tool("tg_pin", "Xabarni qadaydi yoki qadoqdan oladi.",
          {"qayerda": str, "id": int, "olinsinmi": bool})
    async def tg_pin(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.pin(
            str(args.get("qayerda", "")), int(args.get("id") or 0),
            unpin=bool(args.get("olinsinmi")),
        ))

    @tool("tg_archive", "Suhbatni arxivga soladi yoki arxivdan oladi.",
          {"qayerda": str, "arxivgami": bool})
    async def tg_archive(args: dict[str, Any]) -> dict[str, Any]:
        on = args.get("arxivgami")
        return await _text(
            tg.archive(str(args.get("qayerda", "")), on=True if on is None else bool(on))
        )

    @tool("tg_mute", "Suhbat bildirishnomalarini o'chiradi yoki qaytaradi.",
          {"qayerda": str, "ochirilsinmi": bool})
    async def tg_mute(args: dict[str, Any]) -> dict[str, Any]:
        on = args.get("ochirilsinmi")
        return await _text(
            tg.mute(str(args.get("qayerda", "")), on=True if on is None else bool(on))
        )

    @tool(
        "tg_folder",
        "Telegram papkasini yaratadi yoki tarkibini o'zgartiradi. `qoshish` va "
        "`olish` — vergul bilan ajratilgan kanal/guruh nomlari. Papka bo'lmasa "
        "yaratiladi. Masalan: nom='Ish', qoshish='Click Jobs, UzDev Jobs'.",
        {"nom": str, "qoshish": str, "olish": str},
    )
    async def tg_folder(args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("nom", "")).strip()
        if not name:
            return _fail("Papka nomi kerak")
        return await _text(tg.folder_set(
            name, add=_list_arg(args.get("qoshish")), remove=_list_arg(args.get("olish")),
        ))

    @tool("tg_folder_delete", "Papkani o'chiradi. Suhbatlar joyida qoladi.", {"nom": str})
    async def tg_folder_delete(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.folder_delete(str(args.get("nom", ""))))

    @tool("tg_delete_messages", "Xabarlarni o'chiradi. `idlar` — vergul bilan.",
          {"qayerda": str, "idlar": str})
    async def tg_delete_messages(args: dict[str, Any]) -> dict[str, Any]:
        ids = _int_list_arg(args.get("idlar"))
        if not ids:
            return _fail("Xabar id lari kerak")
        return await _text(tg.delete_messages(str(args.get("qayerda", "")), ids))

    @tool(
        "tg_delete_chat",
        "Suhbatni o'chiradi. `hammadanmi` true bo'lsa — kanal/guruh BUTUNLAY "
        "o'chadi va qaytarib bo'lmaydi (faqat yaratuvchi qila oladi).",
        {"qayerda": str, "hammadanmi": bool},
    )
    async def tg_delete_chat(args: dict[str, Any]) -> dict[str, Any]:
        return await _text(tg.delete_chat(
            str(args.get("qayerda", "")), everyone=bool(args.get("hammadanmi")),
        ))

    return [tg_me, tg_chats, tg_read, tg_search, tg_members, tg_folders,
            tg_send, tg_forward, tg_create, tg_invite, tg_promote, tg_demote,
            tg_kick, tg_unban, tg_join, tg_leave, tg_rename, tg_link, tg_pin,
            tg_archive, tg_mute, tg_folder, tg_folder_delete,
            tg_delete_messages, tg_delete_chat]


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
            memory.remember(
                f"ozgarish_{selfwork.stamp()}", result[:400], "o'zgarishlar"
            )
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
        *_telegram_tools(),
        *_self_tools(bus, memory),
    ]
    return create_sdk_mcp_server(name=SERVER_NAME, version="0.3.0", tools=tools)


def read_only_tool_names() -> list[str]:
    """Tasdiq so'ramasdan ishlatsa bo'ladigan asboblarning to'liq nomlari."""
    return [f"mcp__{SERVER_NAME}__{name}" for name in READ_ONLY_TOOLS]
