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

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Tasdiq so'raydigan asboblar — ishonch rejimida shular o'zgaradi.
GATED_TOOLS = ("Write", "Edit", "Bash", "NotebookEdit")


def apply(mode: str) -> int:
    """`on` — so'ramasdan bajaradi, `off` — har safar so'raydi."""
    from .config import ensure_user_config
    from .configpatch import patch_file

    if mode not in ("on", "off"):
        print(f"{RED}Ishlatilishi: python -m jarvis trust on|off{RESET}", file=sys.stderr)
        return 2

    try:
        path = ensure_user_config()
    except OSError as exc:
        print(f"{RED}Sozlama faylini tayyorlab bo'lmadi: {exc}{RESET}", file=sys.stderr)
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
