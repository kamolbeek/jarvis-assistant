"""Telegram — shaxsiy akkaunt (MTProto).

Buni `channels.py` dagi bot bilan aralashtirmang. Bot — alohida shaxs: u
faqat o'ziga /start yozganlarga yoza oladi, sizning chatlaringizni umuman
ko'rmaydi. Bu yerdagi ulanish esa sizning **o'z akkauntingiz**: Jarvis
xabarlaringizni o'qiy oladi va tanishlaringizga sizning nomingizdan yoza
oladi.

Shuning uchun uchta qoida ataylab qo'yilgan:

  * kirish faqat qo'lda — `python -m jarvis telegram-login`. api_id,
    api_hash, telefon raqam, Telegramdan kelgan kod va ikki bosqichli
    parolni siz terminalga o'zingiz kiritasiz; ular na Jarvisga, na modelga
    ko'rinmaydi va repozitoriyga tushmaydi;
  * seans fayli repozitoriydan tashqarida (`~/.jarvis/`) va faqat egasi
    o'qiy oladigan huquq bilan saqlanadi — u kuchi bo'yicha parolga teng;
  * yuborishdan oldin Telegram ilovasi o'sha chatda ochiladi — xabar ko'z
    oldingizda paydo bo'ladi. Tasdiq so'ralmaydi (u yo'lni sekinlashtiradi),
    lekin xato ketsa «tahrirla» yoki «o'chir» deyish yetadi: oxirgi
    yuborilgan xabar eslab qolinadi.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("jarvis.tools.telegram_user")

# Seans va kalitlar repozitoriydan tashqarida turadi — `git` ularni ko'rmasin.
STATE_DIR = Path.home() / ".jarvis"
SESSION_PATH = STATE_DIR / "telegram.session"
CREDENTIALS_PATH = STATE_DIR / "telegram.json"

# Ismni chatlar ro'yxatidan qidirganda shuncha oxirgi chat ko'riladi.
DIALOG_SCAN = 200

INSTALL_HINT = (
    "Telethon kutubxonasi yo'q. O'rnating:\n"
    "  source .venv/bin/activate && pip install -e ."
)
LOGIN_HINT = (
    "Telegram akkauntga kirilmagan. Terminalda bir marta bajaring:\n"
    "  python -m jarvis telegram-login"
)


class TelegramUserError(RuntimeError):
    """Shaxsiy Telegram akkaunti bilan ishlab bo'lmadi."""


def _load_dotenv() -> None:
    """Repozitoriydagi `.env` ni muhitga qo'yadi (mavjud qiymatlar ustun)."""
    try:
        from dotenv import load_dotenv  # noqa: PLC0415 — faqat kerak bo'lganda

        from ..config import REPO_ROOT  # noqa: PLC0415 — aylanma importdan qochish
    except ImportError:  # pragma: no cover — muhitga bog'liq
        return
    load_dotenv(REPO_ROOT / ".env")


def _import_telethon() -> Any:
    try:
        import telethon  # noqa: PLC0415 — ixtiyoriy bog'liqlik
    except ImportError as exc:  # pragma: no cover — muhitga bog'liq
        raise TelegramUserError(INSTALL_HINT) from exc
    return telethon


def load_credentials() -> tuple[int, str]:
    """api_id / api_hash ni topadi: avval muhit o'zgaruvchilari, keyin fayl.

    `.env` ni ham o'qiymiz: `.env.example` da bu ikki qator turibdi, ya'ni
    odam ularni o'sha yerga yozishi tabiiy. Yadro `.env` ni o'zi yuklaydi,
    lekin `telegram-login` yadrosiz ishlaydi.
    """
    _load_dotenv()

    api_id = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()

    if not (api_id and api_hash) and CREDENTIALS_PATH.exists():
        try:
            saved = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TelegramUserError(f"{CREDENTIALS_PATH} o'qilmadi: {exc}") from exc
        api_id = api_id or str(saved.get("api_id", "")).strip()
        api_hash = api_hash or str(saved.get("api_hash", "")).strip()

    if not api_id or not api_hash:
        raise TelegramUserError(
            "api_id / api_hash topilmadi.\n"
            "my.telegram.org > API development tools dan oling, so'ng:\n"
            "  python -m jarvis telegram-login"
        )
    if not api_id.isdigit():
        raise TelegramUserError(f"api_id raqam bo'lishi kerak, hozir: «{api_id[:20]}»")
    return int(api_id), api_hash


def save_credentials(api_id: int, api_hash: str) -> None:
    """api_id / api_hash ni faqat egasi o'qiy oladigan faylga yozadi."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(
        json.dumps({"api_id": int(api_id), "api_hash": api_hash}, indent=2),
        encoding="utf-8",
    )
    CREDENTIALS_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)


def is_logged_in() -> bool:
    """Seans fayli bormi? (Haqiqiy tekshirish — `me()`, bu esa arzon belgi.)"""
    return SESSION_PATH.exists() and SESSION_PATH.stat().st_size > 0


def new_client(api_id: int | None = None, api_hash: str = "") -> Any:
    """Ulanmagan Telethon mijozini yaratadi (login oqimi ham shuni ishlatadi)."""
    telethon = _import_telethon()
    if api_id is None:
        api_id, api_hash = load_credentials()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Telethon `.session` qo'shimchasini o'zi qo'yadi.
    return telethon.TelegramClient(str(SESSION_PATH.with_suffix("")), api_id, api_hash)


# --- Ulanishni bir marta ochib, qayta ishlatamiz ---

_client: Any = None
_lock = asyncio.Lock()


async def get_client() -> Any:
    """Kirilgan mijozni qaytaradi. Kirilmagan bo'lsa — tushunarli xato."""
    global _client

    async with _lock:
        if _client is not None and _client.is_connected():
            return _client

        if not is_logged_in():
            raise TelegramUserError(LOGIN_HINT)

        client = new_client()
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise TelegramUserError(LOGIN_HINT)
        except TelegramUserError:
            await _safe_disconnect(client)
            raise
        except Exception as exc:  # noqa: BLE001 — sabab foydalanuvchiga kerak
            await _safe_disconnect(client)
            raise TelegramUserError(f"Telegramga ulanib bo'lmadi: {exc}") from exc

        _client = client
        return client


async def _safe_disconnect(client: Any) -> None:
    try:
        result = client.disconnect()
        if asyncio.iscoroutine(result):
            await result
    except Exception:  # noqa: BLE001 — yopishdagi xato muhim emas
        log.debug("Telegram ulanishini yopishda xato", exc_info=True)


async def disconnect(client: Any) -> None:
    """Bitta mijozni yopadi (login oqimi shuni ishlatadi)."""
    await _safe_disconnect(client)


async def close() -> None:
    """Dastur tugaganda ulanishni yopadi."""
    global _client
    if _client is not None:
        await _safe_disconnect(_client)
        _client = None


# --- Manzilni aniqlash ---


def _looks_like_handle(who: str) -> bool:
    """@username, +998..., yoki raqamli ID."""
    return who.startswith("@") or who.startswith("+") or who.lstrip("-").isdigit()


def _name_of(entity: Any) -> str:
    """Foydalanuvchi/guruh nomini o'qiladigan ko'rinishda beradi."""
    title = getattr(entity, "title", None)
    if title:
        return str(title)
    parts = [getattr(entity, "first_name", None), getattr(entity, "last_name", None)]
    name = " ".join(str(p) for p in parts if p).strip()
    if name:
        return name
    username = getattr(entity, "username", None)
    return f"@{username}" if username else str(getattr(entity, "id", "?"))


# Tashqaridan ishlatish uchun ochiq nom.
name_of = _name_of


async def resolve(client: Any, who: str) -> tuple[Any, str]:
    """Ism/username bo'yicha chatni topadi va (entity, ko'rinadigan nom) qaytaradi.

    Ataylab qattiqqo'l: bir nechta odam mos kelsa, o'zi tanlab yubormaydi —
    ro'yxatni qaytaradi. Noto'g'ri odamga ketgan xabarni qaytarib bo'lmaydi.
    """
    target = who.strip()
    if not target:
        raise TelegramUserError("Kimga yozishni ayting")

    if target.lower() in ("men", "o'zim", "ozim", "menga", "saved", "me"):
        return "me", "Saqlangan xabarlar"

    if _looks_like_handle(target):
        try:
            entity = await client.get_entity(target)
        except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
            raise TelegramUserError(f"«{target}» topilmadi: {exc}") from exc
        return entity, _name_of(entity)

    needle = target.casefold()
    exact: list[Any] = []
    partial: list[Any] = []
    async for dialog in client.iter_dialogs(limit=DIALOG_SCAN):
        name = (dialog.name or "").casefold()
        if not name:
            continue
        if name == needle:
            exact.append(dialog)
        elif needle in name:
            partial.append(dialog)

    matches = exact or partial
    if not matches:
        raise TelegramUserError(
            f"«{target}» chatlaringiz orasidan topilmadi. "
            f"@username yoki telefon raqamini bering."
        )
    if len(matches) > 1:
        names = ", ".join(d.name for d in matches[:8])
        raise TelegramUserError(
            f"«{target}» bir nechta chatga mos keldi: {names}. Aniqroq ayting."
        )

    dialog = matches[0]
    return dialog.entity, dialog.name


# Oxirgi yuborilgan xabar: (entity, message_id, chat nomi).
#
# Tasdiq so'ramaslikning narxi shu: xato ketishi mumkin. Shuning uchun
# yuborilgan xabarni eslab qolamiz — «tahrirla» yoki «o'chir» deyilganda
# aynan shu xabar ustida ishlanadi.
_last_sent: tuple[Any, int, str] | None = None


async def open_chat(entity: Any) -> bool:
    """Telegram ilovasini o'sha chatda ochadi. Ochilsa True.

    Bu tasdiq so'rashning o'rnini bosadi: xabar ko'z oldingizda paydo
    bo'ladi, ya'ni nima yozilganini o'zingiz ko'rasiz.
    """
    username = getattr(entity, "username", None)
    user_id = getattr(entity, "id", None)

    if username:
        url = f"tg://resolve?domain={username}"
    elif user_id:
        url = f"tg://openmessage?user_id={user_id}"
    else:
        url = ""

    try:
        args = ["open", url] if url else ["open", "-a", "Telegram"]
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await process.wait()
        return process.returncode == 0
    except OSError:
        log.debug("Telegram ilovasi ochilmadi", exc_info=True)
        return False


# --- Amallar ---


async def me() -> str:
    """Qaysi akkauntga kirilgan."""
    client = await get_client()
    user = await client.get_me()
    handle = f" (@{user.username})" if getattr(user, "username", None) else ""
    return f"{_name_of(user)}{handle}"


async def list_chats(limit: int = 15, unread_only: bool = False) -> list[dict[str, Any]]:
    """Oxirgi chatlar: kim, nechta o'qilmagan, oxirgi xabar."""
    client = await get_client()
    chats: list[dict[str, Any]] = []
    scan = DIALOG_SCAN if unread_only else max(1, limit)
    async for dialog in client.iter_dialogs(limit=scan):
        if unread_only and not dialog.unread_count:
            continue
        message = dialog.message
        chats.append({
            "kim": dialog.name or "?",
            "oqilmagan": int(dialog.unread_count or 0),
            "oxirgi_xabar": (getattr(message, "text", "") or "")[:200],
            "vaqt": _when(message),
        })
        if len(chats) >= max(1, limit):
            break
    return chats


async def read_chat(who: str, limit: int = 15) -> dict[str, Any]:
    """Bitta chatning oxirgi xabarlari (eskisidan yangisiga)."""
    client = await get_client()
    entity, name = await resolve(client, who)

    messages: list[dict[str, Any]] = []
    async for message in client.iter_messages(entity, limit=max(1, limit)):
        text = getattr(message, "text", "") or ""
        if not text:
            # Rasm/ovoz xabarini ham ko'rsatamiz — chat mantiqi uzilmasin.
            text = f"[{type(getattr(message, 'media', None)).__name__}]" if message.media else ""
        messages.append({
            "kim": "Siz" if message.out else name,
            "matn": text[:1000],
            "vaqt": _when(message),
        })
    messages.reverse()
    return {"chat": name, "xabarlar": messages}


async def send_as_me(who: str, text: str, show: bool = True) -> str:
    """Sizning nomingizdan xabar yuboradi.

    `show` — yuborishdan oldin Telegram ilovasini o'sha chatda ochadi. Tartib
    muhim: avval ochamiz, keyin yuboramiz — shunda xabar ko'rinib turgan
    chatga tushadi va siz uni paydo bo'lishini ko'rasiz.
    """
    global _last_sent

    body = text.strip()
    if not body:
        raise TelegramUserError("Xabar matni bo'sh")

    client = await get_client()
    entity, name = await resolve(client, who)

    if show:
        await open_chat(entity)

    try:
        message = await client.send_message(entity, body)
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        raise TelegramUserError(f"Xabar ketmadi: {exc}") from exc

    _last_sent = (entity, int(getattr(message, "id", 0)), name)
    log.info("Telegram (shaxsiy) xabari yuborildi: %s (%d belgi)", name, len(body))
    return name


def last_sent() -> tuple[Any, int, str] | None:
    """Oxirgi yuborilgan xabar: (entity, id, chat nomi) yoki None."""
    return _last_sent


async def edit_last(text: str) -> str:
    """Oxirgi yuborilgan xabarni tahrirlaydi. Chat nomini qaytaradi."""
    body = text.strip()
    if not body:
        raise TelegramUserError("Yangi matn bo'sh")
    if _last_sent is None:
        raise TelegramUserError("Bu seansda hali xabar yuborilmagan")

    entity, message_id, name = _last_sent
    client = await get_client()
    try:
        await client.edit_message(entity, message_id, body)
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        # Telegram eski xabarni tahrirlashga ruxsat bermaydi (48 soat).
        raise TelegramUserError(f"Tahrirlab bo'lmadi: {exc}") from exc

    log.info("Telegram xabari tahrirlandi: %s", name)
    return name


async def undo_last() -> str:
    """Oxirgi yuborilgan xabarni ikkala tomondan olib tashlaydi.

    Xato ketgan xabarni qaytarish yo'li shu — tasdiq so'ramaslikning
    o'rniga aynan shu imkoniyat bor.
    """
    global _last_sent

    if _last_sent is None:
        raise TelegramUserError("Bu seansda hali xabar yuborilmagan")

    entity, message_id, name = _last_sent
    client = await get_client()
    try:
        # revoke=True — qabul qiluvchining ekranidan ham yo'qoladi.
        await client.delete_messages(entity, [message_id], revoke=True)
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        raise TelegramUserError(f"Olib tashlab bo'lmadi: {exc}") from exc

    _last_sent = None
    log.info("Telegram xabari olib tashlandi: %s", name)
    return name


# --- Qidiruv --------------------------------------------------------------
#
# «Bir vaqtlar Asadga tashlagan edim» degan gap qidiruvning eng tipik
# ko'rinishi: qaysi chat ekani esda yo'q, faqat so'z esda. Shuning uchun
# `chat` bo'sh bo'lsa butun akkaunt bo'ylab qidiriladi.


async def search(query: str, chat: str = "", limit: int = 20) -> dict[str, Any]:
    """Xabarlar ichidan matn bo'yicha qidiradi.

    `chat` berilsa — faqat o'sha chatda, bo'lmasa — hamma yozishmalarda.
    Saqlangan xabarlar uchun: chat="men".
    """
    needle = query.strip()
    if not needle:
        raise TelegramUserError("Qidiruv so'zi kerak")

    client = await get_client()

    entity: Any = None
    where = "hamma chatlar"
    if chat:
        entity, where = await resolve(client, chat)

    found: list[dict[str, Any]] = []
    try:
        async for message in client.iter_messages(entity, search=needle, limit=max(1, limit)):
            found.append({
                "chat": _chat_name(message) if entity is None else where,
                "kim": "Siz" if getattr(message, "out", False) else _sender_name(message),
                "matn": (getattr(message, "text", "") or "")[:400],
                "vaqt": _when(message),
            })
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        raise TelegramUserError(f"Qidirib bo'lmadi: {exc}") from exc

    return {"soz": needle, "qayerda": where, "topildi": len(found), "xabarlar": found}


def _chat_name(message: Any) -> str:
    """Xabar qaysi chatdan kelgani — global qidiruv natijasi uchun."""
    chat = getattr(message, "chat", None)
    return _name_of(chat) if chat is not None else ""


def _sender_name(message: Any) -> str:
    sender = getattr(message, "sender", None)
    return _name_of(sender) if sender is not None else ""


# --- Fayl yuborish --------------------------------------------------------


async def send_file(
    who: str,
    path: str,
    caption: str = "",
    *,
    video_note: bool = False,
    show: bool = True,
) -> str:
    """Fayl (rasm, video, hujjat) yuboradi.

    `video_note=True` — dumaloq video. Telegram uni faqat kvadrat va qisqa
    (60 s gacha) mp4 dan yasay oladi; mos kelmasa xatoni o'zi aytadi.
    """
    global _last_sent

    source = Path(os.path.expandvars(path)).expanduser()
    if not source.exists():
        raise TelegramUserError(f"Fayl topilmadi: {source}")
    if source.is_dir():
        raise TelegramUserError(f"Bu papka, fayl emas: {source}")

    client = await get_client()
    entity, name = await resolve(client, who)

    if show:
        await open_chat(entity)

    try:
        message = await client.send_file(
            entity, str(source), caption=caption.strip() or None, video_note=video_note
        )
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        raise TelegramUserError(f"Fayl ketmadi: {exc}") from exc

    _last_sent = (entity, int(getattr(message, "id", 0)), name)
    log.info("Telegram fayli yuborildi: %s (%s)", name, source.name)
    return name


# --- So'rovnoma -----------------------------------------------------------


async def send_poll(
    who: str, question: str, options: list[str], multiple: bool = False
) -> str:
    """So'rovnoma yuboradi (guruh yoki kanalga)."""
    title = question.strip()
    answers = [str(o).strip() for o in options if str(o).strip()]
    if not title:
        raise TelegramUserError("Savol matni kerak")
    if len(answers) < 2:
        raise TelegramUserError("Kamida ikkita javob varianti kerak")

    telethon = _import_telethon()
    types_ = telethon.tl.types

    def _text(value: str) -> Any:
        # Telegram yangi qatlamlarda matnni TextWithEntities sifatida
        # kutadi, eskilarida oddiy satr. Ikkalasini ham qo'llab-quvvatlaymiz.
        wrapper = getattr(types_, "TextWithEntities", None)
        return wrapper(text=value, entities=[]) if wrapper else value

    poll = types_.Poll(
        id=random.getrandbits(63),
        question=_text(title),
        answers=[
            types_.PollAnswer(text=_text(answer), option=bytes([index]))
            for index, answer in enumerate(answers)
        ],
        hash=0,
        multiple_choice=multiple or None,
    )

    client = await get_client()
    entity, name = await resolve(client, who)
    await open_chat(entity)

    try:
        await client.send_file(entity, types_.InputMediaPoll(poll=poll))
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        raise TelegramUserError(f"So'rovnoma ketmadi: {exc}") from exc

    log.info("Telegram so'rovnomasi yuborildi: %s", name)
    return name


# --- Umumiy manzara -------------------------------------------------------


async def overview(limit: int = 200, quiet_days: int = 30) -> dict[str, Any]:
    """Akkauntning qisqa tahlili: nima ko'p, nima o'qilmagan, nima jim turibdi.

    «Jim kanallar» ro'yxati ataylab bor: «keraksiz kanallardan chiq» degan
    qarorni taxmin bilan emas, sana bilan qabul qilish kerak.
    """
    client = await get_client()

    total = unread_chats = unread_messages = 0
    people = groups = channels = 0
    top: list[dict[str, Any]] = []
    quiet: list[dict[str, Any]] = []
    threshold = datetime.now(timezone.utc) - timedelta(days=max(1, quiet_days))

    async for dialog in client.iter_dialogs(limit=max(1, limit)):
        total += 1
        count = int(getattr(dialog, "unread_count", 0) or 0)
        if count:
            unread_chats += 1
            unread_messages += count
            top.append({"kim": dialog.name or "?", "oqilmagan": count})

        if getattr(dialog, "is_channel", False) and not getattr(dialog, "is_group", False):
            channels += 1
            last = getattr(getattr(dialog, "message", None), "date", None)
            if last is not None and last < threshold:
                quiet.append({"kanal": dialog.name or "?", "oxirgi_xabar": _when(dialog.message)})
        elif getattr(dialog, "is_group", False):
            groups += 1
        else:
            people += 1

    top.sort(key=lambda row: row["oqilmagan"], reverse=True)
    return {
        "jami_chatlar": total,
        "shaxsiy": people,
        "guruhlar": groups,
        "kanallar": channels,
        "oqilmagan_chatlar": unread_chats,
        "oqilmagan_xabarlar": unread_messages,
        "eng_kop_oqilmagan": top[:10],
        f"jim_kanallar_{quiet_days}_kun": quiet[:15],
    }


# --- Guruh va kanallar ----------------------------------------------------


async def leave(who: str) -> str:
    """Guruh yoki kanaldan chiqadi."""
    client = await get_client()
    entity, name = await resolve(client, who)
    try:
        await client.delete_dialog(entity)
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        raise TelegramUserError(f"Chiqib bo'lmadi: {exc}") from exc

    log.info("Telegram: chiqildi — %s", name)
    return name


async def create_group(title: str, members: list[str], about: str = "",
                       broadcast: bool = False) -> str:
    """Guruh (yoki `broadcast=True` bo'lsa kanal) yaratadi."""
    name = title.strip()
    if not name:
        raise TelegramUserError("Nom kerak")

    telethon = _import_telethon()
    functions = telethon.tl.functions

    client = await get_client()
    users = await _resolve_users(client, members)

    try:
        # Kanal/superguruh sifatida yaratamiz: oddiy guruhning imkoniyati
        # kam va u baribir keyin superguruhga o'tkaziladi.
        result = await client(functions.channels.CreateChannelRequest(
            title=name,
            about=about.strip(),
            megagroup=not broadcast,
            broadcast=broadcast or None,
        ))
        created = result.chats[0]
        if users:
            await client(functions.channels.InviteToChannelRequest(created, users))
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        raise TelegramUserError(f"Yaratib bo'lmadi: {exc}") from exc

    kind = "Kanal" if broadcast else "Guruh"
    log.info("Telegram: %s yaratildi — %s (%d a'zo)", kind.lower(), name, len(users))
    return f"{kind} yaratildi: {name}" + (f" — {len(users)} kishi qo'shildi" if users else "")


async def add_members(chat: str, members: list[str]) -> str:
    """Guruh yoki kanalga odam qo'shadi."""
    client = await get_client()
    entity, name = await resolve(client, chat)
    users = await _resolve_users(client, members)
    if not users:
        raise TelegramUserError("Kimni qo'shishni ayting")

    telethon = _import_telethon()
    functions = telethon.tl.functions

    try:
        await client(functions.channels.InviteToChannelRequest(entity, users))
    except Exception as exc:  # noqa: BLE001 — eski (superguruh bo'lmagan) chat
        try:
            for user in users:
                await client(functions.messages.AddChatUserRequest(
                    chat_id=entity.id, user_id=user, fwd_limit=10,
                ))
        except Exception:  # noqa: BLE001 — sabab birinchi xatoda aniqroq
            raise TelegramUserError(f"Qo'shib bo'lmadi: {exc}") from exc

    log.info("Telegram: %s ga %d kishi qo'shildi", name, len(users))
    return f"{name}: {len(users)} kishi qo'shildi"


async def _resolve_users(client: Any, members: list[str]) -> list[Any]:
    """Ism/username ro'yxatini Telegram foydalanuvchilariga aylantiradi."""
    users: list[Any] = []
    for member in members or []:
        target = str(member).strip()
        if not target:
            continue
        entity, _ = await resolve(client, target)
        users.append(entity)
    return users


def _when(message: Any) -> str:
    date = getattr(message, "date", None)
    if date is None:
        return ""
    try:
        return date.astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):  # pragma: no cover — vaqt mintaqasi buzuq bo'lsa
        return str(date)


# --- Papkalar ---------------------------------------------------------------
#
# Papkalar (Telegram atamasida «dialog filters») bot API'da umuman yo'q —
# bu mijoz xususiyati. Shuning uchun ular aynan shu yerda: akkaunt ulangani
# uchungina «kanallarni papkaga yig'» degan ish bajarilishi mumkin.

# Papka identifikatori 1..255 oralig'ida. 0 va 1 tizimniki (barcha chatlar
# va arxiv), shuning uchun o'zimizniki 2 dan boshlanadi.
FIRST_FOLDER_ID = 2
MAX_FOLDER_ID = 255


def _folder_title(item: Any) -> str:
    """Papka nomi.

    Yangi Telegram qatlamlarida nom `TextWithEntities` (emoji va formatlash
    uchun), eskilarida oddiy satr. Telethon versiyasiga qarab ikkalasi ham
    kelishi mumkin — ikkovini ham o'qiymiz, aks holda kutubxona yangilangan
    kuni papkalar ro'yxati bo'sh nomlar bilan chiqadi.
    """
    title = getattr(item, "title", "")
    return str(getattr(title, "text", title) or "")


def _make_folder_title(types: Any, name: str) -> Any:
    """Nomni joriy Telethon kutadigan ko'rinishga keltiradi."""
    if hasattr(types, "TextWithEntities"):
        return types.TextWithEntities(text=name, entities=[])
    return name


def _peer_key(peer: Any) -> tuple[str, int]:
    """Ikki `InputPeer` ni solishtirish uchun barqaror kalit.

    `access_hash` ni qo'shmaymiz: u seansga bog'liq va o'zgarishi mumkin,
    ya'ni bir xil kanal ikki xil kalit olib, papkaga ikki marta tushardi.
    """
    for attr in ("channel_id", "chat_id", "user_id"):
        value = getattr(peer, attr, None)
        if value is not None:
            return attr, int(value)
    return type(peer).__name__, 0


async def _raw_filters(client: Any) -> list[Any]:
    telethon = _import_telethon()
    result = await client(telethon.tl.functions.messages.GetDialogFiltersRequest())
    # Yangi Telethon `DialogFilters` obyektini, eskisi oddiy ro'yxatni qaytaradi.
    return list(getattr(result, "filters", result) or [])


def _free_folder_id(existing: list[Any]) -> int:
    used = {int(getattr(item, "id", 0)) for item in existing}
    for candidate in range(FIRST_FOLDER_ID, MAX_FOLDER_ID + 1):
        if candidate not in used:
            return candidate
    raise TelegramUserError("Papkalar soni chegaraga yetgan — birortasini o'chiring")


async def folders() -> list[dict[str, Any]]:
    """Papkalar va ularning ichidagi chatlar."""
    telethon = _import_telethon()
    types = telethon.tl.types
    client = await get_client()

    out: list[dict[str, Any]] = []
    for item in await _raw_filters(client):
        if isinstance(item, types.DialogFilterDefault):
            continue
        names: list[str] = []
        peers = list(getattr(item, "pinned_peers", [])) + list(
            getattr(item, "include_peers", [])
        )
        for peer in peers:
            try:
                names.append(_name_of(await client.get_entity(peer)))
            except Exception:  # noqa: BLE001 — bitta chat o'chib ketgan bo'lishi mumkin
                names.append("?")
        out.append({
            "nom": _folder_title(item),
            "nechta": len(peers),
            "chatlar": names,
            "tahrirlanadi": isinstance(item, types.DialogFilter),
        })
    return out


async def _folder_targets(
    client: Any, names: list[str], dialogs: list[Any] | None = None
) -> list[tuple[Any, str]]:
    """Nomlar ro'yxatini chatlarga aylantiradi.

    `resolve` har chaqiruvda chatlar ro'yxatini qaytadan aylanadi. O'n ikkita
    kanalni papkaga solish o'n ikki marta shunday aylanish degani edi —
    shuning uchun ro'yxat bir marta olinadi va chaqiruvlar orasida uzatiladi.
    """
    found: list[tuple[Any, str]] = []
    for raw in names:
        target = str(raw).strip()
        if not target:
            continue
        if _looks_like_handle(target):
            entity, name = await resolve(client, target)
            found.append((entity, name))
            continue

        if dialogs is None:
            dialogs = [d async for d in client.iter_dialogs(limit=DIALOG_SCAN)]

        needle = target.casefold()
        exact = [d for d in dialogs if (d.name or "").casefold() == needle]
        partial = [d for d in dialogs if needle in (d.name or "").casefold()]
        matches = exact or partial
        if not matches:
            raise TelegramUserError(
                f"«{target}» chatlaringiz orasidan topilmadi. "
                f"Avval o'sha kanalga qo'shiling yoki @username bering."
            )
        if len(matches) > 1:
            listed = ", ".join(d.name for d in matches[:8])
            raise TelegramUserError(
                f"«{target}» bir nechta chatga mos keldi: {listed}. Aniqroq ayting."
            )
        found.append((matches[0].entity, matches[0].name))
    return found


async def _dialog_cache(client: Any, names: list[str]) -> list[Any] | None:
    """Nomlar orasida qidirish kerak bo'lsa, chatlar ro'yxatini bir marta oladi."""
    if not any(n.strip() and not _looks_like_handle(n.strip()) for n in names):
        return None
    return [d async for d in client.iter_dialogs(limit=DIALOG_SCAN)]


async def folder_set(name: str, add: list[str] | None = None,
                     remove: list[str] | None = None) -> str:
    """Papkani yaratadi yoki tarkibini o'zgartiradi.

    Bitta funksiya, chunki «papka och va ichiga shularni sol» — bu bitta
    fikr. Papka bo'lmasa yaratiladi, bo'lsa ustiga qo'shiladi.
    """
    title = str(name).strip()
    if not title:
        raise TelegramUserError("Papka nomi kerak")

    telethon = _import_telethon()
    types, functions = telethon.tl.types, telethon.tl.functions
    client = await get_client()

    existing = await _raw_filters(client)
    needle = title.casefold()
    current = next((f for f in existing if _folder_title(f).casefold() == needle), None)

    if current is not None and not isinstance(current, types.DialogFilter):
        raise TelegramUserError(
            f"«{title}» — umumiy (ulashilgan) papka, uni Jarvis tahrirlay olmaydi"
        )

    include = list(getattr(current, "include_peers", [])) if current else []
    pinned = list(getattr(current, "pinned_peers", [])) if current else []
    exclude = list(getattr(current, "exclude_peers", [])) if current else []

    dialogs = await _dialog_cache(client, list(add or []) + list(remove or []))

    added: list[str] = []
    for entity, chat_name in await _folder_targets(client, add or [], dialogs):
        peer = await client.get_input_entity(entity)
        if _peer_key(peer) in {_peer_key(p) for p in include + pinned}:
            continue
        include.append(peer)
        added.append(chat_name)

    removed: list[str] = []
    for entity, chat_name in await _folder_targets(client, remove or [], dialogs):
        peer = await client.get_input_entity(entity)
        key = _peer_key(peer)
        before = len(include) + len(pinned)
        include = [p for p in include if _peer_key(p) != key]
        pinned = [p for p in pinned if _peer_key(p) != key]
        if before != len(include) + len(pinned):
            removed.append(chat_name)

    if not include and not pinned:
        raise TelegramUserError("Papka bo'sh qolmasligi kerak — ichiga chat qo'shing")

    folder_id = current.id if current else _free_folder_id(existing)
    new_filter = types.DialogFilter(
        id=folder_id,
        title=_make_folder_title(types, title),
        pinned_peers=pinned,
        include_peers=include,
        exclude_peers=exclude,
        # Toifa bo'yicha avtomatik qo'shish yoqilmaydi: papka aynan sanab
        # o'tilgan chatlardan iborat bo'lsin, aks holda ichiga begona
        # narsalar o'zi tushib turadi.
        contacts=False, non_contacts=False, groups=False,
        broadcasts=False, bots=False,
        exclude_muted=False, exclude_read=False, exclude_archived=False,
    )

    try:
        await client(functions.messages.UpdateDialogFilterRequest(
            id=folder_id, filter=new_filter,
        ))
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        # Telegram cheklovini o'z nomi bilan aytamiz: «FILTERS_TOO_MUCH»
        # foydalanuvchiga hech nima demaydi.
        kind = type(exc).__name__
        if "FiltersTooMuch" in kind:
            raise TelegramUserError(
                "Papkalar soni chegaraga yetdi — Premium'siz akkauntda 10 ta "
                "papka mumkin. Keraksizini o'chiring."
            ) from exc
        if "FilterIncludeEmpty" in kind:
            raise TelegramUserError("Papka bo'sh bo'lishi mumkin emas") from exc
        raise TelegramUserError(f"Papkani saqlab bo'lmadi: {exc}") from exc

    log.info("Telegram: «%s» papkasi — %d ta chat", title, len(include) + len(pinned))
    parts = [f"«{title}» papkasi {'yaratildi' if current is None else 'yangilandi'}"]
    if added:
        parts.append("qo'shildi: " + ", ".join(added))
    if removed:
        parts.append("olib tashlandi: " + ", ".join(removed))
    parts.append(f"jami {len(include) + len(pinned)} ta chat")
    return ". ".join(parts)


async def folder_delete(name: str) -> str:
    """Papkani o'chiradi. Chatlarning o'ziga tegmaydi."""
    telethon = _import_telethon()
    client = await get_client()

    needle = str(name).strip().casefold()
    current = next(
        (f for f in await _raw_filters(client)
         if needle and needle in _folder_title(f).casefold()),
        None,
    )
    if current is None:
        raise TelegramUserError(f"«{name}» nomli papka topilmadi")

    await client(telethon.tl.functions.messages.UpdateDialogFilterRequest(
        id=current.id, filter=None,
    ))
    log.info("Telegram: «%s» papkasi o'chirildi", _folder_title(current))
    return f"«{_folder_title(current)}» papkasi o'chirildi (chatlar joyida qoldi)"


# --- A'zolar va huquqlar ----------------------------------------------------


async def members(chat: str, limit: int = 50, query: str = "") -> list[dict[str, Any]]:
    """Guruh yoki kanal a'zolari."""
    client = await get_client()
    entity, _ = await resolve(client, chat)
    try:
        people = await client.get_participants(
            entity, limit=max(1, min(int(limit), 200)), search=query,
        )
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"A'zolarni ko'rib bo'lmadi: {exc}") from exc

    return [
        {
            "ism": _name_of(person),
            "username": f"@{person.username}" if person.username else "",
            "bot": bool(person.bot),
        }
        for person in people
    ]


async def promote(chat: str, who: str, rank: str = "", full: bool = False) -> str:
    """Admin qiladi. `full` — u ham boshqalarni admin qila olsin."""
    client = await get_client()
    entity, chat_name = await resolve(client, chat)
    person, person_name = await resolve(client, who)
    try:
        await client.edit_admin(
            entity, person,
            change_info=True, post_messages=True, edit_messages=True,
            delete_messages=True, ban_users=True, invite_users=True,
            pin_messages=True, manage_call=True,
            add_admins=bool(full), title=rank or None,
        )
    except Exception as exc:  # noqa: BLE001 — huquq yoki maxfiylik
        raise TelegramUserError(f"Admin qilib bo'lmadi: {exc}") from exc

    log.info("Telegram: %s — %s da admin", person_name, chat_name)
    return f"{person_name} endi «{chat_name}» da admin"


async def demote(chat: str, who: str) -> str:
    """Adminlikdan oladi (guruhdan chiqarmaydi)."""
    client = await get_client()
    entity, chat_name = await resolve(client, chat)
    person, person_name = await resolve(client, who)
    try:
        await client.edit_admin(entity, person, is_admin=False)
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"Adminlikdan olib bo'lmadi: {exc}") from exc
    return f"{person_name} endi «{chat_name}» da admin emas"


async def kick(chat: str, who: str, ban: bool = False) -> str:
    """Chiqarib yuboradi. `ban` — qaytib kira olmaydigan qilib."""
    client = await get_client()
    entity, chat_name = await resolve(client, chat)
    person, person_name = await resolve(client, who)
    try:
        if ban:
            await client.edit_permissions(entity, person, view_messages=False)
        else:
            await client.kick_participant(entity, person)
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"Chiqarib bo'lmadi: {exc}") from exc

    log.info("Telegram: %s — %s dan chiqarildi (ban=%s)", person_name, chat_name, ban)
    return f"{person_name} «{chat_name}» dan {'bloklandi' if ban else 'chiqarildi'}"


async def unban(chat: str, who: str) -> str:
    """Bloklangan odamni blokdan chiqaradi."""
    client = await get_client()
    entity, chat_name = await resolve(client, chat)
    person, person_name = await resolve(client, who)
    try:
        await client.edit_permissions(entity, person, view_messages=True)
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"Blokdan chiqarib bo'lmadi: {exc}") from exc
    return f"{person_name} «{chat_name}» da blokdan chiqarildi"


# --- Chatning o'zi ----------------------------------------------------------


async def join(target: str) -> str:
    """Kanal yoki guruhga qo'shiladi. Maxfiy taklifnoma havolasi ham bo'ladi."""
    telethon = _import_telethon()
    functions = telethon.tl.functions
    client = await get_client()

    text = str(target).strip()
    code = ""
    lowered = text.lower()
    if "t.me/+" in lowered:
        code = text.split("t.me/+", 1)[1].split("/")[0].split("?")[0]
    elif "t.me/joinchat/" in lowered:
        code = text.split("joinchat/", 1)[1].split("/")[0].split("?")[0]

    try:
        if code:
            result = await client(functions.messages.ImportChatInviteRequest(code))
            entity = result.chats[0]
            name = _name_of(entity)
        else:
            if "t.me/" in lowered:
                text = "@" + text.rstrip("/").rsplit("/", 1)[-1]
            entity, name = await resolve(client, text)
            await client(functions.channels.JoinChannelRequest(entity))
    except Exception as exc:  # noqa: BLE001 — havola eskirgan bo'lishi mumkin
        raise TelegramUserError(f"Qo'shilib bo'lmadi: {exc}") from exc

    log.info("Telegram: qo'shildi — %s", name)
    return f"«{name}» ga qo'shildingiz"


async def invite_link(chat: str) -> str:
    """Taklifnoma havolasini oladi (yoki yaratadi)."""
    telethon = _import_telethon()
    client = await get_client()
    entity, name = await resolve(client, chat)
    try:
        result = await client(
            telethon.tl.functions.messages.ExportChatInviteRequest(peer=entity)
        )
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"Havola olinmadi: {exc}") from exc
    link = str(getattr(result, "link", "") or "")
    return f"«{name}»: {link}" if link else f"«{name}» uchun havola chiqmadi"


async def rename(chat: str, title: str = "", about: str = "") -> str:
    """Guruh/kanal nomini yoki tavsifini o'zgartiradi."""
    telethon = _import_telethon()
    types, functions = telethon.tl.types, telethon.tl.functions
    client = await get_client()
    entity, name = await resolve(client, chat)

    done: list[str] = []
    try:
        if title.strip():
            if isinstance(entity, types.Channel):
                await client(functions.channels.EditTitleRequest(entity, title.strip()))
            else:
                await client(functions.messages.EditChatTitleRequest(
                    entity.id, title.strip(),
                ))
            done.append(f"nomi «{title.strip()}»")
        if about.strip():
            await client(functions.messages.EditChatAboutRequest(
                peer=entity, about=about.strip(),
            ))
            done.append("tavsifi yangilandi")
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"O'zgartirib bo'lmadi: {exc}") from exc

    if not done:
        raise TelegramUserError("Yangi nom yoki tavsif kerak")
    return f"«{name}»: " + ", ".join(done)


async def pin(chat: str, message_id: int, unpin: bool = False) -> str:
    """Xabarni qadaydi yoki qadoqdan oladi."""
    client = await get_client()
    entity, name = await resolve(client, chat)
    try:
        if unpin:
            await client.unpin_message(entity, message_id)
        else:
            await client.pin_message(entity, message_id)
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"Bajarib bo'lmadi: {exc}") from exc
    return f"«{name}»: xabar {'qadoqdan olindi' if unpin else 'qadaldi'}"


async def archive(chat: str, on: bool = True) -> str:
    """Chatni arxivga soladi yoki arxivdan oladi."""
    client = await get_client()
    entity, name = await resolve(client, chat)
    await client.edit_folder(entity, folder=1 if on else 0)
    return f"«{name}» {'arxivga solindi' if on else 'arxivdan olindi'}"


async def mute(chat: str, on: bool = True) -> str:
    """Bildirishnomalarni o'chiradi yoki qaytaradi."""
    telethon = _import_telethon()
    types, functions = telethon.tl.types, telethon.tl.functions
    client = await get_client()
    entity, name = await resolve(client, chat)
    # 2**31-1 — Telegramda «abadiy» ma'nosini beradigan vaqt belgisi.
    await client(functions.account.UpdateNotifySettingsRequest(
        peer=types.InputNotifyPeer(entity),
        settings=types.InputPeerNotifySettings(mute_until=2**31 - 1 if on else 0),
    ))
    return f"«{name}» {'ovozsiz qilindi' if on else 'ovozi qaytarildi'}"


async def forward(source: str, message_ids: list[int], target: str) -> str:
    """Xabarlarni bir chatdan boshqasiga uzatadi."""
    client = await get_client()
    src, src_name = await resolve(client, source)
    dst, dst_name = await resolve(client, target)
    if not message_ids:
        raise TelegramUserError("Qaysi xabarlarni uzatishni ayting")
    try:
        await client.forward_messages(dst, message_ids, src)
    except Exception as exc:  # noqa: BLE001 — xabar o'chirilgan bo'lishi mumkin
        raise TelegramUserError(f"Uzatib bo'lmadi: {exc}") from exc
    return f"{src_name} → {dst_name}: {len(message_ids)} ta xabar uzatildi"


async def delete_messages(chat: str, message_ids: list[int]) -> str:
    """Xabarlarni o'chiradi (hammada)."""
    client = await get_client()
    entity, name = await resolve(client, chat)
    if not message_ids:
        raise TelegramUserError("Qaysi xabarlarni o'chirishni ayting")
    await client.delete_messages(entity, message_ids, revoke=True)
    log.info("Telegram: %s dan %d ta xabar o'chirildi", name, len(message_ids))
    return f"«{name}»: {len(message_ids)} ta xabar o'chirildi"


async def delete_chat(chat: str, everyone: bool = False) -> str:
    """Chatni o'chiradi.

    `everyone=True` — kanal/guruh BUTUNLAY o'chadi (faqat yaratuvchi qila
    oladi va qaytarib bo'lmaydi). Aks holda faqat sizdan o'chadi.
    """
    telethon = _import_telethon()
    types, functions = telethon.tl.types, telethon.tl.functions
    client = await get_client()
    entity, name = await resolve(client, chat)

    try:
        if everyone and isinstance(entity, types.Channel):
            await client(functions.channels.DeleteChannelRequest(entity))
            log.warning("Telegram: «%s» butunlay o'chirildi", name)
            return f"«{name}» butunlay o'chirildi"
        await client.delete_dialog(entity)
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"O'chirib bo'lmadi: {exc}") from exc

    log.warning("Telegram: «%s» o'chirildi (faqat sizda)", name)
    return f"«{name}» o'chirildi (faqat sizda)"


# --- Odamlar: bloklash va kontaktlar ----------------------------------------


async def block(who: str, unblock: bool = False) -> str:
    """Odamni bloklaydi yoki blokdan chiqaradi.

    Guruhdan chiqarish bilan aralashtirmang: bu butun akkaunt darajasida —
    u sizga umuman yoza olmaydi va profilingizni ko'rmaydi.
    """
    telethon = _import_telethon()
    functions = telethon.tl.functions
    client = await get_client()
    entity, name = await resolve(client, who)

    request = functions.contacts.UnblockRequest if unblock else functions.contacts.BlockRequest
    try:
        await client(request(entity))
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        raise TelegramUserError(f"Bajarib bo'lmadi: {exc}") from exc

    log.info("Telegram: %s — %s", name, "blokdan chiqarildi" if unblock else "bloklandi")
    return f"{name} {'blokdan chiqarildi' if unblock else 'bloklandi'}"


async def blocked_list(limit: int = 50) -> list[str]:
    """Bloklanganlar ro'yxati."""
    telethon = _import_telethon()
    client = await get_client()
    result = await client(telethon.tl.functions.contacts.GetBlockedRequest(
        offset=0, limit=max(1, min(int(limit), 100)),
    ))
    return [_name_of(user) for user in getattr(result, "users", [])]


async def contacts_list(query: str = "") -> list[dict[str, Any]]:
    """Telegram kontaktlari (Jarvisning o'z aloqalar daftari emas)."""
    telethon = _import_telethon()
    client = await get_client()
    result = await client(telethon.tl.functions.contacts.GetContactsRequest(hash=0))

    needle = query.strip().casefold()
    rows: list[dict[str, Any]] = []
    for user in getattr(result, "users", []):
        name = _name_of(user)
        if needle and needle not in name.casefold():
            continue
        rows.append({
            "ism": name,
            "username": f"@{user.username}" if user.username else "",
            "telefon": user.phone or "",
        })
    return rows


async def contact_add(phone: str, first_name: str, last_name: str = "") -> str:
    """Telefon raqami bo'yicha kontakt qo'shadi."""
    telethon = _import_telethon()
    functions, types = telethon.tl.functions, telethon.tl.types
    client = await get_client()

    number = phone.strip()
    if not number:
        raise TelegramUserError("Telefon raqam kerak")

    result = await client(functions.contacts.ImportContactsRequest([
        types.InputPhoneContact(
            client_id=0, phone=number,
            first_name=first_name.strip() or number, last_name=last_name.strip(),
        )
    ]))
    if not getattr(result, "users", []):
        raise TelegramUserError(
            f"{number} Telegramda topilmadi (yoki maxfiylik sozlamasi to'sdi)"
        )
    return f"Kontakt qo'shildi: {_name_of(result.users[0])}"


async def contact_delete(who: str) -> str:
    """Kontaktni o'chiradi. Chat va yozishmalar joyida qoladi."""
    telethon = _import_telethon()
    client = await get_client()
    entity, name = await resolve(client, who)
    await client(telethon.tl.functions.contacts.DeleteContactsRequest([entity]))
    return f"{name} kontaktlardan o'chirildi"


# --- Xabar ustidagi amallar -------------------------------------------------


async def react(chat: str, message_id: int, emoji: str = "👍", remove: bool = False) -> str:
    """Xabarga reaksiya qo'yadi yoki olib tashlaydi."""
    telethon = _import_telethon()
    functions, types = telethon.tl.functions, telethon.tl.types
    client = await get_client()
    entity, name = await resolve(client, chat)

    reaction = None if remove else [types.ReactionEmoji(emoticon=emoji)]
    try:
        await client(functions.messages.SendReactionRequest(
            peer=entity, msg_id=int(message_id), reaction=reaction,
        ))
    except Exception as exc:  # noqa: BLE001 — emoji qo'llab-quvvatlanmasligi mumkin
        raise TelegramUserError(f"Reaksiya qo'yib bo'lmadi: {exc}") from exc

    return f"«{name}»: reaksiya {'olindi' if remove else emoji}"


async def mark_read(chat: str) -> str:
    """Chatni o'qilgan deb belgilaydi."""
    client = await get_client()
    entity, name = await resolve(client, chat)
    await client.send_read_acknowledge(entity)
    return f"«{name}» o'qilgan deb belgilandi"


async def send_gif(chat: str, query: str) -> str:
    """GIF yuboradi: @gif inline botidan qidiradi.

    Telegram mijozlari ham aynan shunday qiladi — GIF qidiruvi alohida API
    emas, o'sha inline bot. Topilmasa, saqlangan GIF'lardan olamiz.
    """
    telethon = _import_telethon()
    functions = telethon.tl.functions
    client = await get_client()
    entity, name = await resolve(client, chat)

    text = query.strip()
    try:
        bot = await client.get_input_entity("gif")
        results = await client(functions.messages.GetInlineBotResultsRequest(
            bot=bot, peer=entity, query=text, offset="",
        ))
        if results.results:
            chosen = random.choice(results.results[:10])
            await client(functions.messages.SendInlineBotResultRequest(
                peer=entity, query_id=results.query_id, id=chosen.id, hide_via=True,
            ))
            await open_chat(entity)
            return f"«{name}» ga GIF yuborildi: {text}"
    except Exception as exc:  # noqa: BLE001 — inline bot javob bermasligi mumkin
        log.warning("GIF qidiruvi ishlamadi: %s", exc)

    saved = await client(functions.messages.GetSavedGifsRequest(hash=0))
    gifs = list(getattr(saved, "gifs", []))
    if not gifs:
        raise TelegramUserError(f"«{text}» uchun GIF topilmadi")
    await client.send_file(entity, random.choice(gifs))
    await open_chat(entity)
    return f"«{name}» ga saqlangan GIF yuborildi"


async def send_later(chat: str, text: str, when: Any) -> str:
    """Xabarni belgilangan vaqtda yuboradi (Telegram o'zi jo'natadi).

    Jarvisning eslatmasidan farqi: kompyuter o'chiq bo'lsa ham yuboriladi,
    chunki xabar Telegram serverida turadi.
    """
    client = await get_client()
    entity, name = await resolve(client, chat)
    if not text.strip():
        raise TelegramUserError("Xabar matni kerak")
    try:
        await client.send_message(entity, text, schedule=when)
    except Exception as exc:  # noqa: BLE001 — vaqt o'tmishda bo'lishi mumkin
        raise TelegramUserError(f"Rejaga qo'yib bo'lmadi: {exc}") from exc
    return f"«{name}» ga rejalashtirildi"


async def scheduled(chat: str) -> list[dict[str, Any]]:
    """Shu chat uchun rejalashtirilgan xabarlar."""
    telethon = _import_telethon()
    client = await get_client()
    entity, _ = await resolve(client, chat)
    result = await client(telethon.tl.functions.messages.GetScheduledHistoryRequest(
        peer=entity, hash=0,
    ))
    return [
        {"id": m.id, "vaqt": _when(m), "matn": (m.message or "")[:200]}
        for m in getattr(result, "messages", [])
    ]


# --- Storiyalar -------------------------------------------------------------


async def story_post(path: str, caption: str = "", everyone: bool = True) -> str:
    """Storiya qo'yadi. `path` — rasm yoki video fayl yo'li."""
    telethon = _import_telethon()
    functions, types = telethon.tl.functions, telethon.tl.types
    client = await get_client()

    source = Path(path).expanduser()
    if not source.exists():
        raise TelegramUserError(f"Fayl topilmadi: {source}")

    uploaded = await client.upload_file(str(source))
    suffix = source.suffix.lower()
    if suffix in (".mp4", ".mov", ".m4v"):
        media = types.InputMediaUploadedDocument(
            file=uploaded, mime_type="video/mp4",
            attributes=[types.DocumentAttributeVideo(
                duration=0, w=0, h=0, supports_streaming=True,
            )],
        )
    else:
        media = types.InputMediaUploadedPhoto(file=uploaded)

    # Kimga ko'rinishi: hammaga yoki faqat kontaktlarga.
    rules = ([types.InputPrivacyValueAllowAll()] if everyone
             else [types.InputPrivacyValueAllowContacts()])

    try:
        await client(functions.stories.SendStoryRequest(
            peer=types.InputPeerSelf(), media=media,
            privacy_rules=rules, caption=caption.strip() or None,
            random_id=random.getrandbits(63),
        ))
    except Exception as exc:  # noqa: BLE001 — Premium yoki format cheklovi
        raise TelegramUserError(f"Storiya qo'yib bo'lmadi: {exc}") from exc

    log.info("Telegram: storiya qo'yildi — %s", source.name)
    return f"Storiya qo'yildi: {source.name}"


async def stories_of(who: str = "men") -> list[dict[str, Any]]:
    """Kimningdir (yoki o'zingizning) faol storiyalaringiz."""
    telethon = _import_telethon()
    client = await get_client()
    entity, name = await resolve(client, who)
    result = await client(telethon.tl.functions.stories.GetPeerStoriesRequest(peer=entity))
    stories = getattr(getattr(result, "stories", None), "stories", [])
    return [
        {
            "id": s.id,
            "kim": name,
            "izoh": (getattr(s, "caption", "") or "")[:200],
            "korilgan": getattr(getattr(s, "views", None), "views_count", 0),
        }
        for s in stories
    ]


async def story_delete(story_ids: list[int]) -> str:
    """O'z storiyalaringizni o'chiradi."""
    telethon = _import_telethon()
    types = telethon.tl.types
    client = await get_client()
    if not story_ids:
        raise TelegramUserError("Qaysi storiyani o'chirishni ayting")
    await client(telethon.tl.functions.stories.DeleteStoriesRequest(
        peer=types.InputPeerSelf(), id=[int(i) for i in story_ids],
    ))
    return f"{len(story_ids)} ta storiya o'chirildi"


# --- Ovozli chat va jonli efir ----------------------------------------------
#
# Halol chegara: Jarvis ovozli chatni OCHADI va jonli efir uchun havola
# beradi, lekin o'zi gapirmaydi va video uzatmaydi. Buning uchun WebRTC
# oqimi kerak — bu alohida katta qism (pytgcalls) va ovozli yordamchining
# mikrofoni bilan to'qnashadi. Efirni OBS yoki shunga o'xshash dastur
# quyidagi havola bilan uzatadi.


async def voice_chat_start(chat: str, title: str = "", rtmp: bool = False) -> str:
    """Guruh/kanalda ovozli chat (yoki efir) ochadi."""
    telethon = _import_telethon()
    functions = telethon.tl.functions
    client = await get_client()
    entity, name = await resolve(client, chat)

    try:
        await client(functions.phone.CreateGroupCallRequest(
            peer=entity, random_id=random.getrandbits(31),
            title=title.strip() or None, rtmp_stream=True if rtmp else None,
        ))
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"Ochib bo'lmadi: {exc}") from exc

    what = "Jonli efir" if rtmp else "Ovozli chat"
    log.info("Telegram: %s ochildi — %s", what.lower(), name)
    return f"«{name}» da {what.lower()} ochildi"


async def voice_chat_stop(chat: str) -> str:
    """Ochiq ovozli chatni yopadi."""
    telethon = _import_telethon()
    functions = telethon.tl.functions
    client = await get_client()
    entity, name = await resolve(client, chat)

    full = await client(functions.channels.GetFullChannelRequest(entity)) \
        if hasattr(entity, "broadcast") else None
    call = getattr(getattr(full, "full_chat", None), "call", None)
    if call is None:
        raise TelegramUserError(f"«{name}» da ochiq ovozli chat yo'q")

    await client(functions.phone.DiscardGroupCallRequest(call=call))
    return f"«{name}» dagi ovozli chat yopildi"


async def live_stream_url(chat: str, new_key: bool = False) -> dict[str, str]:
    """Jonli efir uchun RTMP havolasi va kaliti (OBS shularni so'raydi)."""
    telethon = _import_telethon()
    functions = telethon.tl.functions
    client = await get_client()
    entity, name = await resolve(client, chat)

    try:
        result = await client(functions.phone.GetGroupCallStreamRtmpUrlRequest(
            peer=entity, revoke=bool(new_key),
        ))
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"Havola olinmadi: {exc}") from exc

    return {"chat": name, "url": result.url, "kalit": result.key}


# --- Profil va akkaunt ------------------------------------------------------


async def profile_set(first_name: str = "", last_name: str = "", bio: str = "") -> str:
    """Ism, familiya va bio'ni o'zgartiradi. Bo'sh maydonlarga tegilmaydi."""
    telethon = _import_telethon()
    client = await get_client()
    if not any((first_name.strip(), last_name.strip(), bio.strip())):
        raise TelegramUserError("Nimani o'zgartirishni ayting")

    await client(telethon.tl.functions.account.UpdateProfileRequest(
        first_name=first_name.strip() or None,
        last_name=last_name.strip() or None,
        about=bio.strip() or None,
    ))
    return "Profil yangilandi"


async def username_set(username: str) -> str:
    """@username ni o'zgartiradi."""
    telethon = _import_telethon()
    client = await get_client()
    handle = username.strip().lstrip("@")
    try:
        await client(telethon.tl.functions.account.UpdateUsernameRequest(handle))
    except Exception as exc:  # noqa: BLE001 — band bo'lishi mumkin
        raise TelegramUserError(f"@{handle} olinmadi: {exc}") from exc
    return f"Endi siz @{handle}"


async def profile_photo(path: str) -> str:
    """Profil rasmini almashtiradi."""
    telethon = _import_telethon()
    client = await get_client()
    source = Path(path).expanduser()
    if not source.exists():
        raise TelegramUserError(f"Fayl topilmadi: {source}")

    uploaded = await client.upload_file(str(source))
    await client(telethon.tl.functions.photos.UploadProfilePhotoRequest(file=uploaded))
    return f"Profil rasmi almashtirildi: {source.name}"


async def sessions() -> list[dict[str, Any]]:
    """Akkauntga kirgan qurilmalar."""
    telethon = _import_telethon()
    client = await get_client()
    result = await client(telethon.tl.functions.account.GetAuthorizationsRequest())
    return [
        {
            "qurilma": f"{a.device_model} · {a.platform} {a.system_version}".strip(),
            "dastur": f"{a.app_name} {a.app_version}".strip(),
            "joy": a.country or "",
            "hozirgi": bool(a.current),
            "hash": str(a.hash),
        }
        for a in getattr(result, "authorizations", [])
    ]


async def session_kill(session_hash: str) -> str:
    """Boshqa qurilmadagi seansni uzadi."""
    telethon = _import_telethon()
    client = await get_client()
    try:
        await client(telethon.tl.functions.account.ResetAuthorizationRequest(
            hash=int(session_hash),
        ))
    except Exception as exc:  # noqa: BLE001 — hozirgi seansni uzib bo'lmaydi
        raise TelegramUserError(f"Uzib bo'lmadi: {exc}") from exc
    return "Seans uzildi"


# Maxfiylik sozlamalarining o'zbekcha nomlari.
PRIVACY_KEYS = {
    "oxirgi_korilgan": "StatusTimestamp",
    "telefon": "PhoneNumber",
    "rasm": "ProfilePhoto",
    "yoshi": "Birthday",
    "bio": "About",
    "uzatish": "Forwards",
    "qongiroq": "PhoneCall",
    "guruhga_qoshish": "ChatInvite",
    "ovozli_xabar": "VoiceMessages",
}


async def privacy_set(what: str, who: str = "hamma") -> str:
    """Maxfiylik sozlamasini o'zgartiradi.

    `what` — PRIVACY_KEYS dagi nom, `who` — hamma | kontaktlar | hech_kim.
    """
    telethon = _import_telethon()
    functions, types = telethon.tl.functions, telethon.tl.types
    client = await get_client()

    key_name = PRIVACY_KEYS.get(what.strip().casefold())
    if key_name is None:
        raise TelegramUserError(
            "Noma'lum sozlama. Mumkin: " + ", ".join(sorted(PRIVACY_KEYS))
        )
    rules = {
        "hamma": types.InputPrivacyValueAllowAll,
        "kontaktlar": types.InputPrivacyValueAllowContacts,
        "hech_kim": types.InputPrivacyValueDisallowAll,
    }
    rule = rules.get(who.strip().casefold())
    if rule is None:
        raise TelegramUserError("`kim` — hamma | kontaktlar | hech_kim")

    await client(functions.account.SetPrivacyRequest(
        key=getattr(types, f"InputPrivacyKey{key_name}")(), rules=[rule()],
    ))
    return f"«{what}» endi: {who}"


# --- Guruh sozlamalari ------------------------------------------------------


async def slow_mode(chat: str, seconds: int = 0) -> str:
    """Sekin rejim: a'zolar shuncha soniyada bir marta yoza oladi. 0 — o'chirish."""
    telethon = _import_telethon()
    client = await get_client()
    entity, name = await resolve(client, chat)
    try:
        await client(telethon.tl.functions.channels.ToggleSlowModeRequest(
            channel=entity, seconds=int(seconds),
        ))
    except Exception as exc:  # noqa: BLE001 — huquq yoki qiymat cheklovi
        raise TelegramUserError(f"O'rnatib bo'lmadi: {exc}") from exc
    if not seconds:
        return f"«{name}»: sekin rejim o'chirildi"
    return f"«{name}»: sekin rejim {seconds} soniya"


async def chat_permissions(chat: str, can_write: bool = True, can_media: bool = True,
                           can_invite: bool = True) -> str:
    """Guruhdagi oddiy a'zolar nima qila olishini belgilaydi."""
    client = await get_client()
    entity, name = await resolve(client, chat)
    try:
        await client.edit_permissions(
            entity,
            send_messages=can_write,
            send_media=can_media, send_stickers=can_media,
            send_gifs=can_media, send_polls=can_media,
            invite_users=can_invite,
        )
    except Exception as exc:  # noqa: BLE001 — huquq yetmasligi mumkin
        raise TelegramUserError(f"O'zgartirib bo'lmadi: {exc}") from exc
    return f"«{name}»: a'zolar huquqlari yangilandi"


async def admin_log(chat: str, limit: int = 20) -> list[dict[str, Any]]:
    """Adminlar jurnali — guruhda kim nima qilgani."""
    telethon = _import_telethon()
    client = await get_client()
    entity, _ = await resolve(client, chat)
    try:
        result = await client(telethon.tl.functions.channels.GetAdminLogRequest(
            channel=entity, q="", max_id=0, min_id=0,
            limit=max(1, min(int(limit), 100)),
        ))
    except Exception as exc:  # noqa: BLE001 — admin bo'lish shart
        raise TelegramUserError(f"Jurnalni ko'rib bo'lmadi: {exc}") from exc

    users = {u.id: _name_of(u) for u in getattr(result, "users", [])}
    return [
        {
            "vaqt": event.date.astimezone().strftime("%Y-%m-%d %H:%M") if event.date else "",
            "kim": users.get(event.user_id, str(event.user_id)),
            "nima": type(event.action).__name__.replace("ChannelAdminLogEventAction", ""),
        }
        for event in getattr(result, "events", [])
    ]


# --- Sovg'alar --------------------------------------------------------------
#
# Bu yerda faqat ikkita amal bor: ro'yxatni ko'rish va NFT sovg'ani boshqa
# odamga o'tkazish. Sotib olish ataylab yo'q — u to'g'ridan-to'g'ri hisobdan
# pul yechadi va xato qilishning oqibati eng og'iri. O'tkazish ham darvozadan
# har safar alohida so'rab o'tadi (`safety.always_ask`), chunki uni qaytarib
# bo'lmaydi.


async def gifts(limit: int = 50) -> list[dict[str, Any]]:
    """Hisobingizdagi sovg'alar."""
    telethon = _import_telethon()
    functions, types = telethon.tl.functions, telethon.tl.types
    client = await get_client()

    try:
        result = await client(functions.payments.GetSavedStarGiftsRequest(
            peer=types.InputPeerSelf(), offset="", limit=max(1, min(int(limit), 100)),
        ))
    except Exception as exc:  # noqa: BLE001 — API versiyasi farq qilishi mumkin
        raise TelegramUserError(f"Sovg'alarni ko'rib bo'lmadi: {exc}") from exc

    rows: list[dict[str, Any]] = []
    for saved in getattr(result, "gifts", []):
        gift = getattr(saved, "gift", None)
        unique = type(gift).__name__ == "StarGiftUnique"
        rows.append({
            "nom": getattr(gift, "title", "") or getattr(gift, "slug", "") or "sovg'a",
            "nft": unique,
            "otkazsa_boladi": bool(getattr(saved, "can_transfer_at", None) is not None
                                   or getattr(saved, "transfer_stars", None) is not None),
            "narxi_stars": getattr(saved, "transfer_stars", 0) or 0,
            "id": getattr(saved, "msg_id", 0),
            "slug": getattr(gift, "slug", ""),
        })
    return rows


async def gift_transfer(gift: str, to: str) -> str:
    """NFT sovg'ani boshqa odamga o'tkazadi.

    Faqat unique (NFT) sovg'alar o'tkaziladi va bu Stars talab qilishi
    mumkin. Qaytarib bo'lmaydi — shuning uchun darvoza har safar so'raydi.
    """
    telethon = _import_telethon()
    functions, types = telethon.tl.functions, telethon.tl.types
    client = await get_client()
    entity, name = await resolve(client, to)

    needle = str(gift).strip().casefold()
    if not needle:
        raise TelegramUserError("Qaysi sovg'ani o'tkazishni ayting")

    result = await client(functions.payments.GetSavedStarGiftsRequest(
        peer=types.InputPeerSelf(), offset="", limit=100,
    ))
    match = None
    for saved in getattr(result, "gifts", []):
        item = getattr(saved, "gift", None)
        label = f"{getattr(item, 'title', '')} {getattr(item, 'slug', '')}".casefold()
        if needle in label:
            match = saved
            break
    if match is None:
        raise TelegramUserError(
            f"«{gift}» nomli sovg'a topilmadi. `telegram_gifts` bilan ro'yxatni ko'ring."
        )
    if type(getattr(match, "gift", None)).__name__ != "StarGiftUnique":
        raise TelegramUserError(
            "Bu oddiy sovg'a — uni o'tkazib bo'lmaydi. Faqat NFT (unique) "
            "sovg'alar boshqa odamga o'tadi."
        )

    saved_id = types.InputSavedStarGiftUser(msg_id=match.msg_id) \
        if hasattr(types, "InputSavedStarGiftUser") else match.msg_id
    try:
        await client(functions.payments.TransferStarGiftRequest(
            stargift=saved_id, to_id=await client.get_input_entity(entity),
        ))
    except Exception as exc:  # noqa: BLE001 — Stars yetmasligi yoki muddat
        raise TelegramUserError(f"O'tkazib bo'lmadi: {exc}") from exc

    log.warning("Telegram: sovg'a o'tkazildi — %s -> %s", gift, name)
    return f"Sovg'a {name} ga o'tkazildi"
