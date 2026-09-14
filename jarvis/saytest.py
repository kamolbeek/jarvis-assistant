"""`jarvis say` — hozirgi sozlama bilan bitta jumlani aytib beradi.

Ovoz o'zgarmaganda savol doim bitta bo'ladi: sozlama haqiqatan
o'zgardimi, yoki eski provayder ishlab turibdimi? Buni quloq bilan
ajratib bo'lmaydi — shuning uchun bu buyruq avval NIMA ishlatilayotganini
yozib ko'rsatadi, keyin o'sha bilan gapiradi.

Mikrofon, uyg'otuvchi so'z va miya kerak emas: faqat ovoz zanjiri.
"""

from __future__ import annotations

import asyncio
import os
import sys

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

PHRASE = "Assalomu alaykum. Men Jarvisman. Bugun nima qilamiz?"

# Provayder ishlashi uchun kerakli kalitlar.
KEYS = {
    "azure": ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION"),
    "elevenlabs": ("ELEVENLABS_API_KEY",),
    "mohir": ("MOHIR_API_KEY",),
}


def main(values: list[str] | None = None) -> int:
    from .config import ensure_config, load_config
    from .voice.tts import Speaker, build_tts

    ensure_config()
    phrase = " ".join(values) if values else PHRASE
    cfg = load_config()
    section = cfg.section("voice.tts")
    provider = str(section.get("provider", "?"))
    voice = str(section.get("voice", "") or "—")

    print(f"Provayder: {BOLD}{provider}{RESET}")
    print(f"Ovoz:      {BOLD}{voice}{RESET}")

    missing = [name for name in KEYS.get(provider, ()) if not os.environ.get(name)]
    if missing:
        print(f"{RED}.env da yetishmayapti: {', '.join(missing)}{RESET}")
        print(f"{YELLOW}Kalit ko'rinmasa provayder ishlamaydi.{RESET}")
        return 1

    for name in KEYS.get(provider, ()):
        value = os.environ.get(name, "")
        shown = value if name.endswith("REGION") else f"{value[:4]}…{value[-4:]}"
        print(f"{DIM}{name} = {shown}{RESET}")

    print()
    print(f"{DIM}Aytilmoqda: «{phrase}»{RESET}")

    async def speak() -> int:
        tts = build_tts(section)
        speaker = Speaker(device=cfg.get("audio.output_device"))
        try:
            await speaker.play(tts.stream(phrase), tts.sample_rate)
        except Exception as exc:  # noqa: BLE001 — sabab foydalanuvchiga kerak
            from .doctor import hint_for

            detail = f"{type(exc).__name__}: {exc}"
            print(f"{RED}{detail}{RESET}", file=sys.stderr)
            advice = hint_for(detail)
            if advice:
                print(f"{YELLOW}{advice}{RESET}", file=sys.stderr)
            return 1
        finally:
            await tts.aclose()
        print(f"{GREEN}Tugadi.{RESET}")
        return 0

    try:
        return asyncio.run(speak())
    except KeyboardInterrupt:
        return 1
