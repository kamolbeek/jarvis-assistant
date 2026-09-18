"""Telegram hisobiga kirish — bir martalik, terminalda.

Nega alohida buyruq. Kirishda Telegram SMS/ilova orqali kod yuboradi va ikki
bosqichli parol so'rashi mumkin. Bu ikkisini modelga aytdirib bo'lmaydi va
aytdirmaslik ham kerak: kod — hisobingizga kirish kaliti. Shuning uchun kirish
faqat siz o'tirgan terminalda, Jarvisning miyasidan butunlay chetda bo'ladi.

    python -m jarvis telegram-login     kirish
    python -m jarvis telegram-logout    chiqish (seans fayli o'chadi)

Natija — `~/.jarvis/telegram.session` fayli. U hisobingizga kalit: birovga
bermang, git'ga qo'shmang (`.gitignore` da bor).
"""

from __future__ import annotations

import asyncio
import sys
from getpass import getpass

from .tools.telegram import SESSION_PATH, TelegramError, build_client, entity_title


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(130) from None


async def _login() -> int:
    from telethon import errors

    client = build_client()
    await client.connect()
    try:
        if await client.is_user_authorized():
            user = await client.get_me()
            print(f"Allaqachon kirgansiz: {entity_title(user)}")
            print("Boshqa hisobga kirish uchun avval: python -m jarvis telegram-logout")
            return 0

        print("\nTelegram hisobiga kirish")
        print("─" * 40)
        phone = _ask("Telefon raqamingiz (+998...): ")
        if not phone:
            print("Raqam kiritilmadi.")
            return 1

        await client.send_code_request(phone)
        print("Kod yuborildi — Telegram ilovangizni qarang (SMS emas, ilovaning o'zida).")
        code = _ask("Kod: ")

        try:
            await client.sign_in(phone, code)
        except errors.SessionPasswordNeededError:
            # Ikki bosqichli himoya yoqilgan — parolni ekranda ko'rsatmaymiz.
            password = getpass("Ikki bosqichli parolingiz: ")
            await client.sign_in(password=password)
        except errors.PhoneCodeInvalidError:
            print("Kod noto'g'ri. Qaytadan urinib ko'ring.")
            return 1
        except errors.PhoneCodeExpiredError:
            print("Kodning muddati o'tib ketgan. Buyruqni qaytadan bajaring.")
            return 1

        user = await client.get_me()
        print(f"\nKirildi: {entity_title(user)}")
        print(f"Seans fayli: {SESSION_PATH}.session")
        print("Endi Jarvis Telegramda siz qila oladigan hamma ishni qila oladi.")
        print("Tekshirish: python -m jarvis doctor\n")
        return 0
    finally:
        await client.disconnect()


async def _logout() -> int:
    session_file = SESSION_PATH.with_suffix(".session")
    if not session_file.exists():
        print("Seans fayli yo'q — kirilmagan.")
        return 0

    client = build_client()
    await client.connect()
    try:
        if await client.is_user_authorized():
            # Telegram tomonida ham uzamiz, aks holda «Aktiv seanslar» da
            # osilib qoladi va fayl o'chsa ham hisobga kirish ochiq qoladi.
            await client.log_out()
    finally:
        await client.disconnect()

    session_file.unlink(missing_ok=True)
    print("Chiqildi, seans fayli o'chirildi.")
    return 0


def main(action: str = "login") -> int:
    try:
        return asyncio.run(_logout() if action == "logout" else _login())
    except TelegramError as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130
