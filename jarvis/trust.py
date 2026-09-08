"""`jarvis trust` — har bir amal uchun tasdiq so'rashni yoqish/o'chirish.

Standart holatda Jarvis fayl yozish va shell buyruqlari uchun tasdiq
so'raydi. Ishonch ortgach bu halaqit bera boshlaydi: «qil» deganingizda
darhol bajarilishi kerak.

Muhim: bu buyruq **hamma himoyani** olib tashlamaydi. Ikkita qatlam
qoladi va ular ataylab tegilmaydi:

  * `forbidden_patterns` — `rm -rf /`, `mkfs`, `sudo rm` kabi amallar
    hech qachon bajarilmaydi, tasdiq ham so'ralmaydi;
  * `writable_roots` — yozish faqat ruxsat etilgan papkalarda.

Ya'ni «ishonch» degani «hamma narsaga ruxsat» emas: qaytarib bo'ladigan
ishlar so'rovsiz bajariladi, qaytarib bo'lmaydiganlari esa baribir
to'sib turiladi.
"""

from __future__ import annotations

import sys
from pathlib import Path

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Tasdiq so'raydigan asboblar — ishonch rejimida shular o'zgaradi.
GATED_TOOLS = ("Write", "Edit", "Bash", "NotebookEdit")


def current() -> str:
    """Hozirgi rejim: "on", "off" yoki "?" (sozlama o'qilmasa).

    Sozlamani yozishdan oldin uni ko'rsata olish kerak — «yoqilganmi yoki
    yo'qmi» degan savolga fayl ichini ochmasdan javob bo'lsin.
    """
    from .config import load_config

    try:
        return "on" if str(load_config().get("safety.default", "ask")) == "allow" else "off"
    except Exception:  # noqa: BLE001 — holat ko'rsatish hech qachon yiqilmasin
        return "?"


def apply(mode: str) -> int:
    """`on` — so'ramasdan bajaradi, `off` — har safar so'raydi."""
    from .config import CONFIG_PATH
    from .configpatch import patch_file

    if mode == "status":
        state = current()
        label = {"on": "YOQILGAN — tasdiq so'ralmaydi",
                 "off": "O'CHIRILGAN — har bir amal tasdiq so'raydi"}.get(state, "noma'lum")
        print(f"Ishonch rejimi: {label}")
        return 0

    if mode not in ("on", "off"):
        print(f"{RED}Ishlatilishi: python -m jarvis trust on|off|status{RESET}",
              file=sys.stderr)
        return 2

    path = Path(CONFIG_PATH)
    if not path.exists():
        print(f"{RED}{path} topilmadi. Avval:\n"
              f"  cp config/jarvis.example.yaml config/jarvis.yaml{RESET}", file=sys.stderr)
        return 1

    policy = "allow" if mode == "on" else "ask"
    try:
        patch_file(path, "safety", {"default": policy})
        patch_file(path, "rules", dict.fromkeys(GATED_TOOLS, policy))
    except Exception as exc:  # noqa: BLE001 — sabab foydalanuvchiga kerak
        print(f"{RED}{type(exc).__name__}: {exc}{RESET}", file=sys.stderr)
        return 1

    if mode == "on":
        print(f"{GREEN}{BOLD}Tasdiq so'ralmaydi.{RESET} «Qil» deganingizda darhol bajaradi.")
        print(f"{DIM}Telegramda sizning nomingizdan xabar yuborish bundan "
              f"mustasno — u har safar so'rayveradi.{RESET}")
        print(f"{DIM}Himoyaning ikki qatlami joyida qoladi:\n"
              f"  • taqiqlangan buyruqlar (rm -rf /, mkfs, sudo rm…) — baribir "
              f"bajarilmaydi\n"
              f"  • yozish faqat `safety.writable_roots` dagi papkalarda\n"
              f"\n"
              f"Qaytarish: python -m jarvis trust off{RESET}")
    else:
        print(f"{GREEN}Tasdiq qaytarildi.{RESET} Har bir yozish va shell amali so'raladi.")

    print(f"{DIM}Jarvisni qayta ishga tushiring — sozlama ishga tushganda "
          f"o'qiladi.{RESET}")
    return 0
