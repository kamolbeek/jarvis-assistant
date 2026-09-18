"""Telegram — to'liq boshqaruv, foydalanuvchining O'Z hisobi orqali.

Nega bot emas. `channels.py` dagi bot faqat bitta ish qila oladi: sizga xabar
yuborish. Bot API'da quyidagilarning HECH BIRI yo'q:

    - suhbatlar ro'yxatini o'qish (bot o'zi a'zo bo'lmagan joyni ko'rmaydi)
    - papkalar (folders) — ular umuman bot API'da mavjud emas, bu mijoz xususiyati
    - kanal yoki guruh yaratish
    - kanalga qo'shilish / chiqish
    - sizning nomingizdan odam qo'shish, admin qilish, chiqarib yuborish

Shuning uchun bu yerda MTProto ishlatiladi (Telethon): Jarvis Telegram'ga xuddi
yana bitta mijoz sifatida — sizning hisobingiz bilan — ulanadi. Ya'ni o'zingiz
qo'lda qila oladigan hamma narsani u ham qila oladi.

Buning narxi bor va uni ochiq aytish kerak:

    1. Seans fayli (`~/.jarvis/telegram.session`) — bu hisobingizga kalit.
       Uni birovga bermang; parol bilan bir xil darajada maxfiy.
    2. Kirish bir marta, TERMINALDA bo'ladi: `python -m jarvis telegram-login`.
       Ovoz orqali kirib bo'lmaydi — SMS kodini modelga aytdirib bo'lmaydi va
       aytdirmaslik kerak ham.
    3. Avtomatlashtirilgan hisob Telegram cheklovlariga tushishi mumkin
       (ayniqsa ko'p odam qo'shish, ko'p xabar yuborishda). Shuning uchun bu
       yerda ommaviy yuborish (spam) uchun asbob ataylab yo'q.

Pul bilan bog'liq amallar (sovg'a, Stars, Premium sotib olish) bu yerda
umuman amalga oshirilmagan — ya'ni Jarvis xato bilan ham pul sarflay olmaydi.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import env, expand

log = logging.getLogger("jarvis.tools.telegram")

# Seans fayli — kirish bir marta qilinadi va shu yerda saqlanadi.
SESSION_PATH = expand("~/.jarvis/telegram")

# Telegram'da papka identifikatori 1..255 oralig'ida; 0 va 1 tizim uchun band
# (0 — barcha suhbatlar, 1 — arxiv), shuning uchun o'zimizniki 2 dan boshlanadi.
FIRST_FOLDER_ID = 2
MAX_FOLDER_ID = 255

# «Menga o'zimga yoz» degani — Saved Messages.
_SELF_WORDS = {"men", "menga", "o'zim", "o'zimga", "ozim", "ozimga", "saved", "izbrannoe"}

_LINK_RE = re.compile(r"(?:https?://)?t\.me/(?:s/)?(?P<name>[^/?\s]+)", re.IGNORECASE)


class TelegramError(RuntimeError):
    """Telegram amalini bajarib bo'lmadi — matni foydalanuvchiga ko'rsatiladi."""


# ---------------------------------------------------------------- ulanish


@dataclass
class _Session:
    """Bitta jarayon uchun bitta ulanish.

    Har bir asbob chaqiruvida qaytadan ulanish qimmat (har safar handshake va
    kalit almashinuvi) va Telegram buni yoqtirmaydi. Shuning uchun ulanish
    bir marta ochiladi va Jarvis ishlagan davomida ochiq turadi.
    """

    client: Any = None
    lock: asyncio.Lock | None = None
    # Suhbatlar ro'yxati keshi. Nom bo'yicha qidirish uchun har safar butun
    # ro'yxatni tarmoqdan olish qimmat: «o'n ikkita kanalni papkaga sol»
    # degan bitta ish o'n ikki marta to'liq skanerlashga aylanardi.
    dialogs: list[Any] = field(default_factory=list)
    dialogs_at: float = 0.0


# Kesh shuncha soniya yashaydi. Qisqa: yangi kanalga qo'shilgandan keyin
# uni darhol topa olish kerak.
DIALOG_CACHE_SEC = 60.0

_session = _Session()


def _import_telethon() -> Any:
    try:
        import telethon
    except ImportError as exc:  # pragma: no cover — muhitga bog'liq
        raise TelegramError(
            "Telethon kutubxonasi o'rnatilmagan. Terminalda bajaring:\n"
            "    source .venv/bin/activate && pip install -e ."
        ) from exc
    return telethon


def credentials() -> tuple[int, str]:
    """`.env` dagi api_id/api_hash. Ular my.telegram.org dan olinadi."""
    api_id = env("TELEGRAM_API_ID").strip()
    api_hash = env("TELEGRAM_API_HASH").strip()
    if not api_id or not api_hash:
        raise TelegramError(
            "Telegram hisobi sozlanmagan. my.telegram.org > API development tools "
            "dan api_id va api_hash oling va .env ga yozing: "
            "TELEGRAM_API_ID, TELEGRAM_API_HASH."
        )
    try:
        return int(api_id), api_hash
    except ValueError as exc:
        raise TelegramError("TELEGRAM_API_ID butun son bo'lishi kerak") from exc


def build_client(session: str | Path | None = None) -> Any:
    """Ulanmagan mijozni yaratadi. Kirish buyrug'i ham shuni ishlatadi."""
    telethon = _import_telethon()
    api_id, api_hash = credentials()
    path = Path(session) if session else SESSION_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # `device_model` — Telegram'ning «Aktiv seanslar» ro'yxatida ko'rinadi.
    # Tanib olish oson bo'lsin: kerak bo'lsa bitta bosishda uzasiz.
    return telethon.TelegramClient(
        str(path), api_id, api_hash,
        device_model="Jarvis", system_version="macOS", app_version="jarvis 0.2",
    )


async def client() -> Any:
    """Ulangan va kirgan mijozni qaytaradi."""
    if _session.lock is None:
        _session.lock = asyncio.Lock()

    async with _session.lock:
        if _session.client is not None and _session.client.is_connected():
            return _session.client

        if not SESSION_PATH.with_suffix(".session").exists():
            raise TelegramError(
                "Telegram hisobi ulanmagan. Terminalda bir marta bajaring:\n"
                "    python -m jarvis telegram-login"
            )

        cl = build_client()
        await cl.connect()
        if not await cl.is_user_authorized():
            await cl.disconnect()
            raise TelegramError(
                "Telegram seansi eskirgan (yoki telefondan uzilgan). "
                "Qaytadan kiring: python -m jarvis telegram-login"
            )
        _session.client = cl
        log.info("Telegram hisobiga ulandi")
        return cl


async def close() -> None:
    """Yadro to'xtaganda ulanishni yopadi."""
    if _session.client is not None:
        try:
            await _session.client.disconnect()
        except Exception:  # pragma: no cover — yopilishda xato muhim emas
            log.debug("Telegram ulanishini yopishda xato", exc_info=True)
        _session.client = None
    _session.dialogs = []
    _session.dialogs_at = 0.0


def forget_dialogs() -> None:
    """Keshni bekor qiladi — yangi kanal qo'shilgandan keyin kerak."""
    _session.dialogs = []
    _session.dialogs_at = 0.0


def is_linked() -> bool:
    """Seans fayli bormi? (Haqiqiy tekshiruv emas — tez javob uchun.)"""
    return SESSION_PATH.with_suffix(".session").exists()


# ---------------------------------------------------------------- manzilni topish


def _looks_like_id(text: str) -> bool:
    return bool(re.fullmatch(r"-?\d{5,}", text))


def describe_kind(entity: Any) -> str:
    """Obyekt turini o'zbekcha bitta so'z bilan."""
    from telethon.tl import types

    if isinstance(entity, types.User):
        return "bot" if entity.bot else "shaxs"
    if isinstance(entity, types.Chat):
        return "guruh"
    if isinstance(entity, types.Channel):
        return "superguruh" if entity.megagroup else "kanal"
    return "suhbat"


def entity_title(entity: Any) -> str:
    """Ko'rsatish uchun nom."""
    title = getattr(entity, "title", None)
    if title:
        return str(title)
    parts = [getattr(entity, "first_name", ""), getattr(entity, "last_name", "")]
    name = " ".join(p for p in parts if p).strip()
    if name:
        return name
    username = getattr(entity, "username", "")
    return f"@{username}" if username else str(getattr(entity, "id", "?"))


async def _all_dialogs(cl: Any) -> list[Any]:
    """Suhbatlar ro'yxati, qisqa muddatli kesh bilan."""
    now = time.monotonic()
    if _session.dialogs and now - _session.dialogs_at < DIALOG_CACHE_SEC:
        return _session.dialogs

    entities = [dialog.entity async for dialog in cl.iter_dialogs()]
    _session.dialogs = entities
    _session.dialogs_at = now
    return entities


async def resolve(target: str) -> Any:
    """Matnni Telegram obyektiga aylantiradi.

    Ovoz orqali ishlashning asosiy qiyinligi shu: foydalanuvchi «Click Jobs»
    deydi, Telegram esa @username yoki raqamli id kutadi. Shuning uchun nom
    bo'yicha qidirish ham qo'llab-quvvatlanadi — lekin bir nechta suhbat mos
    kelsa, taxmin qilinmaydi: ro'yxat qaytariladi va model aniqlashtiradi.
    Noto'g'ri guruhga yozib yuborishdan ko'ra qayta so'ragan afzal.
    """
    text = str(target or "").strip()
    if not text or text.lower() in _SELF_WORDS:
        return "me"

    cl = await client()

    link = _LINK_RE.search(text)
    if link:
        name = link.group("name")
        if name.startswith("+") or name.lower() == "joinchat":
            raise TelegramError(
                "Bu maxfiy taklifnoma havolasi — avval `tg_join` bilan qo'shiling."
            )
        text = "@" + name

    if text.startswith("@") or _looks_like_id(text):
        try:
            return await cl.get_entity(int(text) if _looks_like_id(text) else text)
        except Exception as exc:
            raise TelegramError(f"«{target}» topilmadi: {exc}") from exc

    # Nom bo'yicha — o'z suhbatlarimiz ichidan.
    needle = text.casefold()
    exact: list[Any] = []
    partial: list[Any] = []
    for entity in await _all_dialogs(cl):
        name = entity_title(entity).casefold()
        if name == needle:
            exact.append(entity)
        elif needle in name:
            partial.append(entity)

    found = exact or partial
    if not found:
        raise TelegramError(
            f"«{target}» nomli suhbat topilmadi. @username bering yoki "
            f"`tg_chats` bilan ro'yxatni ko'ring."
        )
    if len(found) > 1:
        names = ", ".join(f"«{entity_title(e)}»" for e in found[:8])
        raise TelegramError(
            f"«{target}» ga bir nechtasi mos keldi: {names}. Qaysi biri kerak?"
        )
    return found[0]


# ---------------------------------------------------------------- o'qish


async def me() -> dict[str, Any]:
    cl = await client()
    user = await cl.get_me()
    return {
        "ism": entity_title(user),
        "username": f"@{user.username}" if user.username else "",
        "telefon": user.phone or "",
        "id": user.id,
    }


async def chats(query: str = "", kind: str = "", limit: int = 60) -> list[dict[str, Any]]:
    """Suhbatlar ro'yxati. `kind`: kanal | guruh | superguruh | shaxs | bot."""
    cl = await client()
    wanted = kind.strip().casefold()
    needle = query.strip().casefold()
    out: list[dict[str, Any]] = []

    async for dialog in cl.iter_dialogs():
        entity = dialog.entity
        row_kind = describe_kind(entity)
        if wanted and row_kind != wanted:
            # «guruh» deganda superguruhlar ham tushunilsin — foydalanuvchi
            # uchun ular bir xil narsa, farqi faqat texnik.
            if not (wanted == "guruh" and row_kind == "superguruh"):
                continue
        name = entity_title(entity)
        if needle and needle not in name.casefold():
            continue
        out.append({
            "nom": name,
            "turi": row_kind,
            "id": entity.id,
            "username": f"@{entity.username}" if getattr(entity, "username", None) else "",
            "oqilmagan": dialog.unread_count,
        })
        if len(out) >= limit:
            break
    return out


async def history(target: str, limit: int = 20) -> list[dict[str, Any]]:
    """Suhbatdagi oxirgi xabarlar (yangisidan eskisiga)."""
    cl = await client()
    entity = await resolve(target)
    out: list[dict[str, Any]] = []
    for message in await cl.get_messages(entity, limit=max(1, min(int(limit), 100))):
        text = (message.message or "").strip()
        if not text and message.media:
            text = "[media]"
        sender = ""
        try:
            author = await message.get_sender()
            if author is not None:
                sender = entity_title(author)
        except Exception:  # kanal nomidan yozilgan xabarda muallif bo'lmasligi mumkin
            sender = ""
        out.append({
            "id": message.id,
            "vaqt": message.date.astimezone().strftime("%Y-%m-%d %H:%M") if message.date else "",
            "kim": sender,
            "matn": text[:1500],
        })
    return out


async def search(query: str, target: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """Xabarlar ichidan qidiradi. `target` bo'sh bo'lsa — hamma suhbatlardan."""
    cl = await client()
    limit = max(1, min(int(limit), 100))
    out: list[dict[str, Any]] = []

    if target:
        entity = await resolve(target)
        messages = await cl.get_messages(entity, limit=limit, search=query)
    else:
        from telethon.tl import functions, types

        result = await cl(functions.messages.SearchGlobalRequest(
            q=query, filter=types.InputMessagesFilterEmpty(),
            min_date=None, max_date=None, offset_rate=0,
            offset_peer=types.InputPeerEmpty(), offset_id=0, limit=limit,
        ))
        messages = result.messages

    for message in messages:
        out.append({
            "id": getattr(message, "id", 0),
            "vaqt": message.date.astimezone().strftime("%Y-%m-%d %H:%M")
            if getattr(message, "date", None) else "",
            "matn": (getattr(message, "message", "") or "")[:800],
        })
    return out


async def members(target: str, limit: int = 50, query: str = "") -> list[dict[str, Any]]:
    """Guruh yoki kanal a'zolari."""
    cl = await client()
    entity = await resolve(target)
    try:
        people = await cl.get_participants(
            entity, limit=max(1, min(int(limit), 200)), search=query
        )
    except Exception as exc:
        raise TelegramError(f"A'zolarni ko'rib bo'lmadi: {exc}") from exc
    return [
        {
            "ism": entity_title(person),
            "username": f"@{person.username}" if person.username else "",
            "id": person.id,
            "bot": bool(person.bot),
        }
        for person in people
    ]


# ---------------------------------------------------------------- yozish


async def send(target: str, text: str) -> str:
    cl = await client()
    entity = await resolve(target)
    await cl.send_message(entity, text)
    return f"«{entity_title(entity) if entity != 'me' else 'Saqlangan xabarlar'}» ga yuborildi"


async def forward(source: str, message_ids: list[int], target: str) -> str:
    cl = await client()
    src = await resolve(source)
    dst = await resolve(target)
    await cl.forward_messages(dst, message_ids, src)
    return f"{len(message_ids)} ta xabar uzatildi"


async def create_chat(
    title: str, about: str = "", broadcast: bool = False, members_: list[str] | None = None
) -> dict[str, Any]:
    """Kanal (broadcast) yoki superguruh yaratadi.

    Oddiy «guruh» emas, superguruh yaratiladi: Telegram allaqachon shunday
    qiladi va faqat superguruhda papka, admin huquqlari va tarix to'liq
    ishlaydi. Foydalanuvchi uchun farqi sezilmaydi.
    """
    from telethon.tl import functions

    cl = await client()
    result = await cl(functions.channels.CreateChannelRequest(
        title=title, about=about or "", megagroup=not broadcast, broadcast=broadcast,
    ))
    entity = result.chats[0]

    added: list[str] = []
    failed: list[str] = []
    if members_:
        added, failed = await _invite(entity, members_)

    # Yangi suhbat keshda yo'q — keyingi «uni papkaga sol» topa olmasdi.
    forget_dialogs()

    link = ""
    try:
        link = await invite_link(entity)
    except TelegramError:
        link = ""

    return {
        "nom": entity_title(entity),
        "turi": describe_kind(entity),
        "id": entity.id,
        "havola": link,
        "qoshilganlar": added,
        "qoshilmaganlar": failed,
    }


def _invite_reason(exc: Exception) -> str:
    """Telethon xatosini foydalanuvchiga tushunarli sababga aylantiradi."""
    name = type(exc).__name__
    if "UserPrivacyRestricted" in name:
        return "maxfiylik sozlamasi ruxsat bermadi"
    if "UserNotMutualContact" in name:
        return "avval u sizni kontaktiga qo'shishi kerak"
    if "UserChannelsTooMuch" in name:
        return "uning kanallari soni chegaraga yetgan"
    if "PeerFlood" in name:
        return "Telegram vaqtincha cheklab qo'ydi — biroz kutish kerak"
    if "UserAlreadyParticipant" in name:
        return "allaqachon a'zo"
    return str(exc)[:120]


async def _invite(entity: Any, users: list[str]) -> tuple[list[str], list[str]]:
    """Odam qo'shishning haqiqiy ishi.

    Har biri alohida qo'shiladi: biri rad etilsa qolganlari qo'shilaveradi.
    Rad etish bu yerda odatiy hol — Telegram maxfiyligi ko'pchilikda yoqilgan
    va uni chetlab o'tish mumkin emas. Shuning uchun sabab ham qaytariladi:
    «qo'shilmadi» degan javob o'zi hech nima tushuntirmaydi.
    """
    from telethon.tl import functions

    cl = await client()
    added: list[str] = []
    failed: list[str] = []
    for name in users:
        try:
            user = await resolve(name)
            await cl(functions.channels.InviteToChannelRequest(entity, [user]))
            added.append(entity_title(user))
        except TelegramError as exc:
            failed.append(f"{name} ({exc})")
        except Exception as exc:
            log.warning("«%s» ni qo'shib bo'lmadi: %s", name, exc)
            failed.append(f"{name} ({_invite_reason(exc)})")
    return added, failed


async def invite(target: str, users: list[str]) -> str:
    entity = await resolve(target)
    added, failed = await _invite(entity, users)
    if not added:
        raise TelegramError(
            "Hech kim qo'shilmadi: " + "; ".join(failed) +
            ". Taklifnoma havolasini yuborib ko'ring."
        )
    message = f"«{entity_title(entity)}» ga qo'shildi: {', '.join(added)}"
    if failed:
        message += f". Qo'shilmadi: {'; '.join(failed)}"
    return message


async def promote(target: str, user: str, rank: str = "", full: bool = False) -> str:
    """Admin qiladi. `full` — boshqa adminlarni tayinlash huquqi ham beriladi."""
    cl = await client()
    entity = await resolve(target)
    person = await resolve(user)
    try:
        await cl.edit_admin(
            entity, person,
            change_info=True, post_messages=True, edit_messages=True,
            delete_messages=True, ban_users=True, invite_users=True,
            pin_messages=True, manage_call=True,
            add_admins=bool(full), title=rank or None,
        )
    except Exception as exc:
        raise TelegramError(f"Admin qilib bo'lmadi: {exc}") from exc
    return f"«{entity_title(person)}» — «{entity_title(entity)}» da admin"


async def demote(target: str, user: str) -> str:
    cl = await client()
    entity = await resolve(target)
    person = await resolve(user)
    try:
        await cl.edit_admin(entity, person, is_admin=False)
    except Exception as exc:
        raise TelegramError(f"Adminlikdan olib bo'lmadi: {exc}") from exc
    return f"«{entity_title(person)}» endi admin emas"


async def kick(target: str, user: str, ban: bool = False) -> str:
    """Chiqarib yuboradi. `ban` — qaytib kira olmaydigan qilib."""
    cl = await client()
    entity = await resolve(target)
    person = await resolve(user)
    try:
        if ban:
            await cl.edit_permissions(entity, person, view_messages=False)
        else:
            await cl.kick_participant(entity, person)
    except Exception as exc:
        raise TelegramError(f"Chiqarib bo'lmadi: {exc}") from exc
    verb = "bloklandi" if ban else "chiqarildi"
    return f"«{entity_title(person)}» — «{entity_title(entity)}» dan {verb}"


async def unban(target: str, user: str) -> str:
    cl = await client()
    entity = await resolve(target)
    person = await resolve(user)
    await cl.edit_permissions(entity, person, view_messages=True)
    return f"«{entity_title(person)}» blokdan chiqarildi"


async def join(target: str) -> str:
    """Kanal/guruhga qo'shiladi. Maxfiy havola (t.me/+...) ham qabul qilinadi."""
    from telethon.tl import functions

    cl = await client()
    text = str(target).strip()
    link = _LINK_RE.search(text)
    code = ""
    if link:
        name = link.group("name")
        if name.startswith("+"):
            code = name[1:]
        elif name.lower() == "joinchat":
            code = text.rstrip("/").rsplit("/", 1)[-1]

    if code:
        result = await cl(functions.messages.ImportChatInviteRequest(code))
        entity = result.chats[0]
    else:
        entity = await resolve(text)
        await cl(functions.channels.JoinChannelRequest(entity))
    forget_dialogs()
    return f"«{entity_title(entity)}» ga qo'shildingiz"


async def leave(target: str) -> str:
    cl = await client()
    entity = await resolve(target)
    await cl.delete_dialog(entity)
    forget_dialogs()
    return f"«{entity_title(entity)}» dan chiqildi"


async def rename(target: str, title: str = "", about: str = "") -> str:
    from telethon.tl import functions, types

    cl = await client()
    entity = await resolve(target)
    done: list[str] = []

    if title:
        if isinstance(entity, types.Channel):
            await cl(functions.channels.EditTitleRequest(entity, title))
        else:
            await cl(functions.messages.EditChatTitleRequest(entity.id, title))
        done.append(f"nomi «{title}»")
    if about:
        await cl(functions.messages.EditChatAboutRequest(peer=entity, about=about))
        done.append("tavsifi yangilandi")

    if not done:
        raise TelegramError("`nom` yoki `tavsif` dan kamida bittasi kerak")
    forget_dialogs()
    return "O'zgartirildi: " + ", ".join(done)


async def invite_link(target: Any) -> str:
    """Taklifnoma havolasini oladi (yoki yaratadi)."""
    from telethon.tl import functions

    cl = await client()
    entity = target if not isinstance(target, str) else await resolve(target)
    try:
        result = await cl(functions.messages.ExportChatInviteRequest(peer=entity))
    except Exception as exc:
        raise TelegramError(f"Havola olinmadi: {exc}") from exc
    return str(getattr(result, "link", "") or "")


async def pin(target: str, message_id: int, unpin: bool = False) -> str:
    cl = await client()
    entity = await resolve(target)
    if unpin:
        await cl.unpin_message(entity, message_id)
        return "Xabar qadoqdan olindi"
    await cl.pin_message(entity, message_id)
    return "Xabar qadaldi"


async def archive(target: str, on: bool = True) -> str:
    cl = await client()
    entity = await resolve(target)
    await cl.edit_folder(entity, folder=1 if on else 0)
    return f"«{entity_title(entity)}» {'arxivga solindi' if on else 'arxivdan olindi'}"


async def mute(target: str, on: bool = True) -> str:
    from telethon.tl import functions, types

    cl = await client()
    entity = await resolve(target)
    # 2**31-1 — Telegram'da «abadiy» ma'nosini beradigan vaqt belgisi.
    await cl(functions.account.UpdateNotifySettingsRequest(
        peer=types.InputNotifyPeer(entity),
        settings=types.InputPeerNotifySettings(mute_until=2**31 - 1 if on else 0),
    ))
    return f"«{entity_title(entity)}» {'ovozsiz qilindi' if on else 'ovozi qaytarildi'}"


async def delete_messages(target: str, message_ids: list[int]) -> str:
    cl = await client()
    entity = await resolve(target)
    await cl.delete_messages(entity, message_ids, revoke=True)
    return f"{len(message_ids)} ta xabar o'chirildi"


async def delete_chat(target: str, everyone: bool = False) -> str:
    """Suhbatni o'chiradi.

    `everyone=True` — kanal/guruh BUTUNLAY o'chadi (faqat yaratuvchi qila oladi,
    qaytarib bo'lmaydi). Aks holda faqat siz chiqasiz/o'chirasiz.
    """
    from telethon.tl import functions, types

    cl = await client()
    entity = await resolve(target)
    name = entity_title(entity)

    if everyone and isinstance(entity, types.Channel):
        await cl(functions.channels.DeleteChannelRequest(entity))
        forget_dialogs()
        return f"«{name}» butunlay o'chirildi"

    await cl.delete_dialog(entity)
    forget_dialogs()
    return f"«{name}» o'chirildi (faqat sizda)"


# ---------------------------------------------------------------- papkalar


def _filter_title(item: Any) -> str:
    """Papka nomi.

    Telegram yangi qatlamlarda nomni `TextWithEntities` sifatida qaytaradi
    (emoji va formatlash uchun), eskilarida oddiy satr. Ikkalasi ham bo'lishi
    mumkin — Telethon versiyasiga bog'liq.
    """
    title = getattr(item, "title", "")
    return str(getattr(title, "text", title) or "")


def _make_title(name: str) -> Any:
    """Nomni joriy Telethon kutadigan ko'rinishga keltiradi."""
    from telethon.tl import types

    if hasattr(types, "TextWithEntities"):
        return types.TextWithEntities(text=name, entities=[])
    return name


def _peer_key(peer: Any) -> tuple[str, int]:
    """Ikki `InputPeer` ni solishtirish uchun barqaror kalit."""
    for attr in ("channel_id", "chat_id", "user_id"):
        value = getattr(peer, attr, None)
        if value is not None:
            return attr, int(value)
    return type(peer).__name__, 0


async def _raw_filters() -> list[Any]:
    from telethon.tl import functions

    cl = await client()
    result = await cl(functions.messages.GetDialogFiltersRequest())
    # Yangi Telethon `DialogFilters` obyektini, eskisi oddiy ro'yxatni qaytaradi.
    return list(getattr(result, "filters", result) or [])


async def folders() -> list[dict[str, Any]]:
    """Papkalar va ularning ichidagi suhbatlar."""
    from telethon.tl import types

    cl = await client()
    out: list[dict[str, Any]] = []
    for item in await _raw_filters():
        if isinstance(item, types.DialogFilterDefault):
            continue
        names: list[str] = []
        for peer in list(getattr(item, "pinned_peers", [])) + list(
            getattr(item, "include_peers", [])
        ):
            try:
                names.append(entity_title(await cl.get_entity(peer)))
            except Exception:
                names.append("?")
        out.append({
            "nom": _filter_title(item),
            "id": item.id,
            "suhbatlar": names,
            "tahrirlanadi": isinstance(item, types.DialogFilter),
        })
    return out


async def _find_filter(name: str) -> Any | None:
    needle = name.strip().casefold()
    for item in await _raw_filters():
        if _filter_title(item).casefold() == needle:
            return item
    # Aniq mos kelmasa — qismini qidiramiz (ovozda nom to'liq aytilmasligi mumkin).
    for item in await _raw_filters():
        if needle and needle in _filter_title(item).casefold():
            return item
    return None


def _free_filter_id(existing: list[Any]) -> int:
    used = {int(getattr(item, "id", 0)) for item in existing}
    for candidate in range(FIRST_FOLDER_ID, MAX_FOLDER_ID + 1):
        if candidate not in used:
            return candidate
    raise TelegramError("Papkalar soni chegaraga yetgan — birortasini o'chiring")


async def folder_set(name: str, add: list[str] | None = None,
                     remove: list[str] | None = None) -> str:
    """Papkani yaratadi yoki tarkibini o'zgartiradi.

    Bitta funksiya, chunki «papka och va ichiga shularni sol» — bu bitta
    fikr. Papka bo'lmasa yaratiladi, bo'lsa ustiga qo'shiladi.
    """
    from telethon.tl import functions, types

    cl = await client()
    existing = await _raw_filters()
    current = None
    needle = name.strip().casefold()
    for item in existing:
        if _filter_title(item).casefold() == needle:
            current = item
            break

    if current is not None and not isinstance(current, types.DialogFilter):
        raise TelegramError(
            f"«{name}» — umumiy (ulashilgan) papka, uni Jarvis tahrirlay olmaydi"
        )

    include = list(getattr(current, "include_peers", [])) if current else []
    pinned = list(getattr(current, "pinned_peers", [])) if current else []
    exclude = list(getattr(current, "exclude_peers", [])) if current else []

    added: list[str] = []
    for target in add or []:
        entity = await resolve(target)
        peer = await cl.get_input_entity(entity)
        keys = {_peer_key(p) for p in include + pinned}
        if _peer_key(peer) in keys:
            continue
        include.append(peer)
        added.append(entity_title(entity))

    removed: list[str] = []
    for target in remove or []:
        entity = await resolve(target)
        peer = await cl.get_input_entity(entity)
        key = _peer_key(peer)
        before = len(include) + len(pinned)
        include = [p for p in include if _peer_key(p) != key]
        pinned = [p for p in pinned if _peer_key(p) != key]
        if before != len(include) + len(pinned):
            removed.append(entity_title(entity))

    if not include and not pinned:
        raise TelegramError("Papka bo'sh qolmasligi kerak — ichiga suhbat qo'shing")

    filter_id = current.id if current else _free_filter_id(existing)
    new_filter = types.DialogFilter(
        id=filter_id,
        title=_make_title(name),
        pinned_peers=pinned,
        include_peers=include,
        exclude_peers=exclude,
        # Papka aynan sanab o'tilgan suhbatlardan iborat bo'lsin — toifalar
        # bo'yicha avtomatik qo'shish yoqilsa, ichiga begona narsalar tushadi.
        contacts=False, non_contacts=False, groups=False,
        broadcasts=False, bots=False,
        exclude_muted=False, exclude_read=False, exclude_archived=False,
    )
    try:
        await cl(functions.messages.UpdateDialogFilterRequest(id=filter_id, filter=new_filter))
    except Exception as exc:
        # Telegram cheklovlarini o'z nomi bilan aytamiz: xom xato matni
        # («FILTERS_TOO_MUCH») foydalanuvchiga hech nima demaydi.
        name = type(exc).__name__
        if "FiltersTooMuch" in name:
            raise TelegramError(
                "Papkalar soni chegaraga yetdi — Premium'siz hisobda 10 ta papka "
                "mumkin. Keraksiz papkani o'chiring."
            ) from exc
        if "FilterIncludeEmpty" in name:
            raise TelegramError("Papka bo'sh bo'lishi mumkin emas") from exc
        if "ChatlistExcludeInvalid" in name or "FilterTitleEmpty" in name:
            raise TelegramError("Papka nomi noto'g'ri") from exc
        raise TelegramError(f"Papkani saqlab bo'lmadi: {exc}") from exc

    what = "yaratildi" if current is None else "yangilandi"
    parts = [f"«{name}» papkasi {what}"]
    if added:
        parts.append(f"qo'shildi: {', '.join(added)}")
    if removed:
        parts.append(f"olib tashlandi: {', '.join(removed)}")
    parts.append(f"jami {len(include) + len(pinned)} ta suhbat")
    return ". ".join(parts)


async def folder_delete(name: str) -> str:
    from telethon.tl import functions

    cl = await client()
    current = await _find_filter(name)
    if current is None:
        raise TelegramError(f"«{name}» nomli papka topilmadi")
    await cl(functions.messages.UpdateDialogFilterRequest(id=current.id, filter=None))
    return f"«{_filter_title(current)}» papkasi o'chirildi (suhbatlar joyida qoldi)"
