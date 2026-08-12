"""macOS bilan ishlash: bildirishnoma, ilovalar, SMS/iMessage, Shortcuts.

Bu yerda telefon bilan bog'lanishning amaliy yo'li ham bor: **Shortcuts**.
iPhone'ni to'liq boshqarib bo'lmaydi (Apple ruxsat bermaydi), lekin Mac'dagi
Shortcuts iCloud orqali telefon bilan sinxronlanadi — shuning uchun Mac'dan
ishga tushirilgan qisqa yo'l telefonda amal bajarishi mumkin.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess

log = logging.getLogger("jarvis.tools.macos")

APPLESCRIPT_TIMEOUT = 20.0


class MacOsError(RuntimeError):
    """macOS amali bajarilmadi."""


async def _run(args: list[str], timeout: float = APPLESCRIPT_TIMEOUT) -> str:
    """Buyruqni bajaradi va stdout qaytaradi."""

    def call() -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)

    try:
        result = await asyncio.to_thread(call)
    except subprocess.TimeoutExpired as exc:
        raise MacOsError(f"Buyruq {timeout:.0f} soniyada tugamadi") from exc
    except FileNotFoundError as exc:
        raise MacOsError(f"`{args[0]}` topilmadi — bu funksiya faqat macOS'da ishlaydi") from exc

    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise MacOsError(message or f"Buyruq {result.returncode} kodi bilan tugadi")
    return result.stdout.strip()


async def osascript(script: str) -> str:
    """AppleScript kodini bajaradi."""
    return await _run(["osascript", "-e", script])


def _quote(text: str) -> str:
    """Matnni AppleScript satriga xavfsiz joylashtiradi."""
    return json.dumps(str(text))


# --- Bildirishnomalar ---

async def notify(title: str, message: str, subtitle: str = "") -> None:
    """macOS bildirishnomasini ko'rsatadi."""
    parts = [f"display notification {_quote(message)}", f"with title {_quote(title)}"]
    if subtitle:
        parts.append(f"subtitle {_quote(subtitle)}")
    await osascript(" ".join(parts))


# --- Ilovalar ---

async def open_app(name: str) -> None:
    """Ilovani ochadi yoki oldinga chiqaradi."""
    await _run(["open", "-a", name])


async def quit_app(name: str) -> None:
    await osascript(f"tell application {_quote(name)} to quit")


async def frontmost_app() -> str:
    """Hozir qaysi ilova faol ekanini qaytaradi."""
    return await osascript(
        'tell application "System Events" to get name of first application process '
        "whose frontmost is true"
    )


async def open_url(url: str) -> None:
    """Havolani standart brauzerda ochadi."""
    if not url.startswith(("http://", "https://")):
        raise MacOsError("Faqat http/https havolalari ochiladi")
    await _run(["open", url])


# --- Xabarlar ---

async def send_imessage(recipient: str, text: str) -> None:
    """Messages ilovasi orqali xabar yuboradi (iMessage yoki SMS).

    `recipient` — telefon raqami yoki Apple ID pochtasi.
    SMS yuborish uchun iPhone'da "Text Message Forwarding" yoqilgan bo'lishi kerak.
    """
    script = (
        'tell application "Messages"\n'
        '  set targetService to 1st account whose service type = iMessage\n'
        f"  set targetBuddy to participant {_quote(recipient)} of targetService\n"
        f"  send {_quote(text)} to targetBuddy\n"
        "end tell"
    )
    await osascript(script)
    log.info("iMessage yuborildi: %s", recipient)


# --- Shortcuts (telefon bilan ko'prik) ---

def shortcuts_available() -> bool:
    return shutil.which("shortcuts") is not None


async def list_shortcuts() -> list[str]:
    """Mavjud qisqa yo'llar ro'yxati."""
    if not shortcuts_available():
        raise MacOsError("`shortcuts` buyrug'i topilmadi (macOS 12+ kerak)")
    output = await _run(["shortcuts", "list"])
    return [line.strip() for line in output.splitlines() if line.strip()]


async def run_shortcut(name: str, input_text: str = "") -> str:
    """Qisqa yo'lni ishga tushiradi va natijasini qaytaradi.

    iCloud orqali sinxronlangan qisqa yo'llar telefonda ham amal bajarishi mumkin —
    shuning uchun "telefonimga eslatma qo'y" kabi ishlar shu orqali qilinadi.
    """
    if not shortcuts_available():
        raise MacOsError("`shortcuts` buyrug'i topilmadi (macOS 12+ kerak)")

    args = ["shortcuts", "run", name]
    if input_text:
        args += ["--input-path", "-"]

        def call() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                args, input=input_text, capture_output=True, text=True, timeout=60.0
            )

        result = await asyncio.to_thread(call)
        if result.returncode != 0:
            raise MacOsError((result.stderr or result.stdout).strip())
        return result.stdout.strip()

    return await _run(args, timeout=60.0)


# --- Tizim ---

async def set_volume(percent: int) -> None:
    """Tizim ovoz balandligini o'rnatadi (0..100)."""
    level = max(0, min(100, int(percent)))
    await osascript(f"set volume output volume {level}")


async def get_volume() -> int:
    """Hozirgi ovoz balandligi (0..100)."""
    raw = await osascript("output volume of (get volume settings)")
    try:
        return max(0, min(100, int(raw.strip())))
    except ValueError as exc:
        raise MacOsError(f"Ovoz balandligi o'qilmadi: {raw!r}") from exc


async def lock_screen() -> None:
    """Ekranni qulflaydi."""
    await osascript(
        'tell application "System Events" to keystroke "q" using {command down, control down}'
    )
