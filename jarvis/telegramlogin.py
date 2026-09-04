"""`jarvis telegram-login` — shaxsiy Telegram akkauntga bir martalik kirish.

Nega alohida buyruq? Chunki bu yerda kiritiladigan narsalar — api_hash,
Telegramdan kelgan kod va ikki bosqichli parol — akkauntning kalitlari.
Ular terminalda, sizning qo'lingizdan kiritiladi: Jarvisning miyasi
(model) ularni ko'rmaydi, jurnalga tushmaydi va repozitoriyga yozilmaydi.

Natijada `~/.jarvis/telegram.session` fayli paydo bo'ladi. O'sha fayl —
kirilgan seans. Uni hech kimga bermang: u parol bilan teng.
Bekor qilish uchun: `jarvis telegram-logout`.
"""

from __future__ import annotations

import asyncio
import sys
from getpass import getpass

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

STEPS = f"""\
{BOLD}Telegram shaxsiy akkauntga ulanish{RESET}

Bu bot emas — bu sizning o'z akkauntingiz. Ulangandan keyin Jarvis
chatlaringizni o'qiy oladi va sizning nomingizdan xabar yubora oladi
(har bir yuborishdan oldin tasdiq so'raydi).

{BOLD}Oldindan:{RESET} brauzerda {BOLD}my.telegram.org{RESET} > API development tools
ga kirib, {BOLD}api_id{RESET} va {BOLD}api_hash{RESET} ni oling.

{DIM}Quyidagilarni faqat siz kiritasiz. Ular modelga ko'rinmaydi.{RESET}
"""

# Kod necha marta so'raladi.
CODE_ATTEMPTS = 3

CODE_HINT = f"""\
{YELLOW}Kod SMS bilan kelmaydi.{RESET} U Telegram ilovasining o'zida, ko'k belgili
rasmiy {BOLD}«Telegram»{RESET} chatiga keladi (arxivda ham bo'lishi mumkin).
{DIM}Har urinishda yangi kod yuboriladi — eski xabardagi kod ishlamaydi.{RESET}"""


def _ask(prompt: str, secret: bool = False) -> str:
    try:
        value = getpass(prompt) if secret else input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        raise
    return value.strip()


async def _login() -> int:
    from .tools import telegram_user as tg

    # Kutubxona yo'qligi hech narsa so'ramasdan oldin ma'lum bo'lsin —
    # api_id va api_hash ni tekinga yozdirishning hojati yo'q.
    try:
        tg._import_telethon()
    except tg.TelegramUserError as exc:
        print(f"{RED}{exc}{RESET}", file=sys.stderr)
        return 1

    print(STEPS)

    try:
        api_id, api_hash = tg.load_credentials()
        print(f"{DIM}api_id / api_hash tayyor (avval saqlangan).{RESET}")
    except tg.TelegramUserError:
        api_id_raw = _ask("api_id (raqam): ")
        if not api_id_raw.isdigit():
            print(f"{RED}api_id faqat raqamlardan iborat bo'lishi kerak.{RESET}", file=sys.stderr)
            return 1
        api_hash = _ask("api_hash: ", secret=True)
        if not api_hash:
            print(f"{RED}api_hash bo'sh.{RESET}", file=sys.stderr)
            return 1
        api_id = int(api_id_raw)

    try:
        client = tg.new_client(api_id, api_hash)
    except tg.TelegramUserError as exc:
        print(f"{RED}{exc}{RESET}", file=sys.stderr)
        return 1

    from telethon import errors  # noqa: PLC0415 — mijoz yaratilgach mavjud

    try:
        await client.connect()

        if await client.is_user_authorized():
            user = await client.get_me()
            print(f"\n{GREEN}Allaqachon kirilgan:{RESET} {tg.name_of(user)}")
            tg.save_credentials(api_id, api_hash)
            return 0

        phone = _ask("Telefon raqam (+998...): ")
        if not phone.startswith("+"):
            print(f"{YELLOW}Raqamni xalqaro ko'rinishda yozing: +998...{RESET}")
        await client.send_code_request(phone)
        print(CODE_HINT)

        # Kod xato bo'lsa yoki eskirsa, butun buyruqni qaytadan boshlash
        # shart emas — bu yerda eng ko'p adashiladi (kod SMS emas, Telegram
        # ilovasiga keladi va har urinishda yangisi yuboriladi).
        for attempt in range(1, CODE_ATTEMPTS + 1):
            last = attempt == CODE_ATTEMPTS
            code = _ask("Telegramdan kelgan kod: ")
            try:
                await client.sign_in(phone, code)
                break
            except errors.SessionPasswordNeededError:
                password = _ask("Ikki bosqichli parol: ", secret=True)
                await client.sign_in(password=password)
                break
            except (errors.PhoneCodeInvalidError, errors.PhoneCodeEmptyError):
                print(f"{YELLOW}Kod noto'g'ri. Telegramdagi eng oxirgi xabarga "
                      f"qarang.{RESET}")
                if last:
                    print(f"{RED}Kod uch marta to'g'ri kelmadi. Buyruqni qaytadan "
                          f"bering.{RESET}", file=sys.stderr)
                    return 1
            except errors.PhoneCodeExpiredError:
                if last:
                    print(f"{RED}Kodning muddati o'tdi. Buyruqni qaytadan bering.{RESET}",
                          file=sys.stderr)
                    return 1
                print(f"{YELLOW}Kodning muddati o'tibdi — yangisini yubordim.{RESET}")
                await client.send_code_request(phone)

        user = await client.get_me()
        tg.save_credentials(api_id, api_hash)
        try:
            tg.SESSION_PATH.chmod(0o600)
        except OSError:
            pass

        print(f"\n{GREEN}{BOLD}Kirildi:{RESET} {tg.name_of(user)}")
        print(f"{DIM}Seans fayli: {tg.SESSION_PATH}{RESET}")
        print(f"{DIM}Endi ayta olasiz: «Telegramda nima yangilik?» yoki\n"
              f"«Ibratga yoz: juma muborak».{RESET}\n")
        return 0

    except errors.PasswordHashInvalidError:
        print(f"{RED}Ikki bosqichli parol noto'g'ri.{RESET}", file=sys.stderr)
        return 1
    except errors.FloodWaitError as exc:
        print(f"{RED}Telegram juda ko'p urinishdan keyin {exc.seconds} soniya "
              f"kutishni so'radi.{RESET}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — sabab foydalanuvchiga kerak
        print(f"{RED}{type(exc).__name__}: {exc}{RESET}", file=sys.stderr)
        return 1
    finally:
        await tg.disconnect(client)


async def _logout() -> int:
    from .tools import telegram_user as tg

    if not tg.is_logged_in():
        print("Kirilmagan — o'chiradigan seans yo'q.")
        return 0

    try:
        client = tg.new_client()
        await client.connect()
        # Telegram tomonida ham seansni bekor qilamiz, keyin faylni o'chiramiz.
        try:
            await client.log_out()
        finally:
            await tg.disconnect(client)
    except Exception as exc:  # noqa: BLE001 — fayl baribir o'chirilsin
        print(f"{YELLOW}Telegramga ulanib bo'lmadi ({exc}). "
              f"Seans fayli baribir o'chiriladi.{RESET}")

    for path in (tg.SESSION_PATH, tg.SESSION_PATH.with_suffix(".session-journal")):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            print(f"{RED}{path} o'chmadi: {exc}{RESET}", file=sys.stderr)
            return 1

    print(f"{GREEN}Chiqildi.{RESET} Seans fayli o'chirildi.")
    print(f"{DIM}api_id / api_hash saqlanib qoldi: {tg.CREDENTIALS_PATH}\n"
          f"Ularni ham olib tashlamoqchi bo'lsangiz, faylni o'chiring.{RESET}")
    return 0


def main(values: list[str] | None = None) -> int:
    action = (values or ["login"])[0] if values else "login"
    try:
        if action == "logout":
            return asyncio.run(_logout())
        return asyncio.run(_login())
    except ImportError as exc:
        print(f"{RED}{exc}{RESET}", file=sys.stderr)
        print("pip install -e '.[telegram]'", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nBekor qilindi.")
        return 1
