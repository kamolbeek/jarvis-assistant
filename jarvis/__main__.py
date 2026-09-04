"""Buyruqlar qatori kirish nuqtasi.

Bu fayl ataylab yengil: modul darajasida faqat standart kutubxona
import qilinadi. Sababi — `doctor` buyrug'i aynan nimadir buzilganda
kerak bo'ladi, shuning uchun u og'ir importlar ortida qolib ketmasligi
kerak. Har bir buyruq o'ziga kerakli narsani o'zi yuklaydi.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

USAGE = """\
Misollar:
  jarvis            Jarvis'ni ishga tushirish
  jarvis doctor     Har bir qismni alohida tekshirish (birinchi ishga tushirishdan oldin)
  jarvis wake-test  Chaqiruv ballini o'lchash va chegarani sozlash
  jarvis mic-test   Mikrofonlarni yonma-yon o'lchash (qaysi biri toza signal beradi)
  jarvis wake-set 0.33 0.25   Chegarani sozlamaga yozish
  jarvis telegram-login   Shaxsiy Telegram akkauntga kirish (bir marta)
  jarvis telegram-logout  Telegram seansini bekor qilish
  jarvis trust on   Har bir amal uchun tasdiq so'ramasin
  jarvis trust off  Tasdiqni qaytarish
  jarvis -v         Batafsil jurnal bilan
"""


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)-22s %(message)s",
        datefmt="%H:%M:%S",
    )
    # Kutubxonalarning shovqinini pasaytiramiz
    for noisy in ("httpx", "httpcore", "websockets", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Ovozli shaxsiy AI yordamchi",
        epilog=USAGE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "doctor", "wake-test", "wake-set", "mic-test", "trust",
                 "telegram-login", "telegram-logout"],
        help="run — ishga tushirish (standart); doctor — diagnostika; "
             "wake-test — chaqiruv ballini o'lchash; wake-set — chegarani yozish; "
             "mic-test — mikrofonlarni o'lchash; "
             "telegram-login / telegram-logout — shaxsiy Telegram akkaunt; "
             "trust on|off — tasdiq so'rashni o'chirish/yoqish",
    )
    parser.add_argument("values", nargs="*", help="wake-set uchun: chegara [shubhali]")
    parser.add_argument("-v", "--verbose", action="store_true", help="Batafsil jurnal")
    args = parser.parse_args()

    if args.command in ("telegram-login", "telegram-logout"):
        logging.basicConfig(level=logging.ERROR)
        from .telegramlogin import main as telegram_main

        return telegram_main(["logout" if args.command == "telegram-logout" else "login"])

    if args.command == "trust":
        from .trust import apply

        return apply(args.values[0] if args.values else "")

    if args.command == "wake-set":
        from .waketune import apply_thresholds

        return apply_thresholds(args.values)

    if args.command == "doctor":
        # Diagnostika o'z natijasini o'zi chiroyli chiqaradi — jurnal xalaqit bermasin.
        logging.basicConfig(level=logging.ERROR)
        from .doctor import main as doctor_main

        return doctor_main()

    if args.command == "wake-test":
        logging.basicConfig(level=logging.ERROR)
        from .waketune import main as wake_main

        return wake_main()

    if args.command == "mic-test":
        logging.basicConfig(level=logging.ERROR)
        from .mictest import main as mic_main

        return mic_main(args.values)

    configure_logging(args.verbose)

    # Og'ir importlar faqat shu yerda — `doctor` ularsiz ham ishlaydi.
    try:
        from .app import amain
    except ImportError as exc:
        print(f"Kutubxona yetishmayapti: {exc}", file=sys.stderr)
        print("`pip install -e .` ni bajaring yoki `jarvis doctor` bilan tekshiring.",
              file=sys.stderr)
        return 1

    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
