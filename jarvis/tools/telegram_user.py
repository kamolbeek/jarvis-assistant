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
  * xabar yuborish har safar tasdiq so'raydi (`trust on` bo'lganda ham) —
    boshqa odamga ketgan xabarni qaytarib bo'lmaydi.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import stat
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
    "  source .venv/bin/activate && pip install -e '.[telegram]'"
)
LOGIN_HINT = (
    "Telegram akkauntga kirilmagan. Terminalda bir marta bajaring:\n"
    "  python -m jarvis telegram-login"
)


class TelegramUserError(RuntimeError):
    """Shaxsiy Telegram akkaunti bilan ishlab bo'lmadi."""


def _import_telethon() -> Any:
    try:
        import telethon  # noqa: PLC0415 — ixtiyoriy bog'liqlik
    except ImportError as exc:  # pragma: no cover — muhitga bog'liq
        raise TelegramUserError(INSTALL_HINT) from exc
    return telethon


def load_credentials() -> tuple[int, str]:
    """api_id / api_hash ni topadi: avval muhit o'zgaruvchilari, keyin fayl."""
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
    async for dialog in client.iter_dialogs(limit=max(1, limit) if not unread_only else DIALOG_SCAN):
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


async def send_as_me(who: str, text: str) -> str:
    """Sizning nomingizdan xabar yuboradi. Chaqirilishidan oldin tasdiq so'raladi."""
    body = text.strip()
    if not body:
        raise TelegramUserError("Xabar matni bo'sh")

    client = await get_client()
    entity, name = await resolve(client, who)
    try:
        await client.send_message(entity, body)
    except Exception as exc:  # noqa: BLE001 — Telethon xatolari xilma-xil
        raise TelegramUserError(f"Xabar ketmadi: {exc}") from exc

    log.info("Telegram (shaxsiy) xabari yuborildi: %s (%d belgi)", name, len(body))
    return name


def _when(message: Any) -> str:
    date = getattr(message, "date", None)
    if date is None:
        return ""
    try:
        return date.astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):  # pragma: no cover — vaqt mintaqasi buzuq bo'lsa
        return str(date)
