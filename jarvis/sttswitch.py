"""`jarvis stt` — nutqni matnga aylantiruvchini almashtirish.

Bu sozlama eng ko'p o'zgartiriladigan qatorlardan biri: har bir provayder
boshqacha muvozanat beradi va qaysi biri to'g'ri kelishini faqat o'z
ovozingiz, o'z mikrofoningiz va o'z internetingiz bilan sinab bilasiz.
Shuning uchun buni YAML faylni qo'lda ochmasdan almashtirish kerak.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

# provayder -> (nomi, kuchli tomoni, kerakli kalit)
PROVIDERS: dict[str, tuple[str, str, str]] = {
    "elevenlabs": (
        "ElevenLabs Scribe",
        "eng aniq va tez; internet va kalit kerak, har so'rov pullik",
        "ELEVENLABS_API_KEY",
    ),
    "mohir": (
        "Mohir.ai",
        "o'zbek tiliga ixtisoslashgan; internet va kalit kerak",
        "MOHIR_API_KEY",
    ),
    "whisper_local": (
        "mlx-whisper (Apple Silicon)",
        "oflayn va bepul; M-seriyali Mac'da tez",
        "",
    ),
    "whisper_cpp": (
        "whisper.cpp / rubaiSTT",
        "oflayn va bepul; aniq, lekin sezilarli kechikish beradi",
        "",
    ),
}

# Odam aytadigan nomlar.
ALIASES = {
    "rubai": "whisper_cpp",
    "rubaistt": "whisper_cpp",
    "whisper": "whisper_local",
    "mlx": "whisper_local",
    "11labs": "elevenlabs",
    "eleven": "elevenlabs",
}


def current() -> str:
    """Hozir qaysi provayder yozilgan."""
    from .config import load_config

    try:
        return str(load_config().get("voice.stt.provider", "?"))
    except Exception:  # noqa: BLE001 — holat ko'rsatish yiqilmasin
        return "?"


def _show() -> int:
    now = current()
    print(f"Hozirgi eshitish: {BOLD}{now}{RESET}")
    print()
    print("Mavjud variantlar:")
    for key, (label, note, _key) in PROVIDERS.items():
        mark = "•" if key != now else ">"
        print(f"  {mark} {key:<14} {label} — {DIM}{note}{RESET}")
    print()
    print(f"{DIM}Almashtirish: python -m jarvis stt whisper_local{RESET}")
    return 0


def apply(values: list[str]) -> int:
    """`jarvis stt [provayder]`. Argumentsiz — hozirgi holatni ko'rsatadi."""
    from .config import CONFIG_PATH
    from .configpatch import patch_file

    if not values:
        return _show()

    choice = ALIASES.get(values[0].strip().lower(), values[0].strip().lower())
    if choice not in PROVIDERS:
        print(f"{RED}Noma'lum provayder: {values[0]}{RESET}", file=sys.stderr)
        print(f"Mumkin: {', '.join(PROVIDERS)}", file=sys.stderr)
        return 2

    path = Path(CONFIG_PATH)
    if not path.exists():
        print(f"{RED}{path} topilmadi. Avval:\n"
              f"  cp config/jarvis.example.yaml config/jarvis.yaml{RESET}", file=sys.stderr)
        return 1

    try:
        patch_file(path, "voice.stt", {"provider": choice}, create=True)
    except Exception as exc:  # noqa: BLE001 — sabab foydalanuvchiga kerak
        print(f"{RED}{type(exc).__name__}: {exc}{RESET}", file=sys.stderr)
        return 1

    label, note, needs_key = PROVIDERS[choice]
    print(f"{GREEN}{BOLD}Eshitish: {label}{RESET}")
    print(f"{DIM}{note}{RESET}")

    # Kalit yo'q bo'lsa, buni hozir aytish kerak — aks holda birinchi
    # chaqiruvda «javob yo'q» bo'lib chiqadi va sababi ko'rinmaydi.
    if needs_key and not os.environ.get(needs_key):
        print(f"{YELLOW}Diqqat: .env da {needs_key} yo'q — u bo'lmasa ishlamaydi.{RESET}")

    print(f"{DIM}Jarvisni qayta ishga tushiring — sozlama ishga tushganda "
          f"o'qiladi.{RESET}")
    return 0
