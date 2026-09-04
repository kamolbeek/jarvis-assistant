"""`jarvis telegram-login` — kod kiritishdagi eng ko'p uchraydigan holatlar.

Kod SMS bilan emas, Telegram ilovasiga keladi va har urinishda yangilanadi.
Shuning uchun xato yoki eskirgan kod butun buyruqni to'xtatib qo'ymasligi
kerak: sikl qaytadan so'raydi, muddati o'tgan bo'lsa yangi kod yuboradi.
"""

from __future__ import annotations

import sys
import types

import pytest


# --- Soxta telethon ----------------------------------------------------------


class _Err(Exception):
    pass


class _SessionPasswordNeededError(_Err):
    pass


class _PhoneCodeInvalidError(_Err):
    pass


class _PhoneCodeEmptyError(_Err):
    pass


class _PhoneCodeExpiredError(_Err):
    pass


class _PasswordHashInvalidError(_Err):
    pass


class _FloodWaitError(_Err):
    def __init__(self, seconds: int = 60) -> None:
        super().__init__("flood")
        self.seconds = seconds


class _FakeTelegramClient:
    """Skript bo'yicha javob beradigan mijoz."""

    def __init__(self, codes: dict[str, object], password: str = "") -> None:
        self.codes = codes           # kiritilgan kod -> None (o'tadi) yoki xato
        self.password = password
        self.code_requests = 0
        self.signed_in = False

    async def connect(self) -> None:
        pass

    async def is_user_authorized(self) -> bool:
        return False

    async def send_code_request(self, phone: str) -> None:
        self.code_requests += 1

    async def sign_in(self, phone: str = "", code: str = "", password: str = ""):
        if password:
            if password != self.password:
                raise _PasswordHashInvalidError()
            self.signed_in = True
            return None
        outcome = self.codes.get(code, _PhoneCodeInvalidError())
        if isinstance(outcome, Exception):
            raise outcome
        self.signed_in = True
        return None

    async def get_me(self):
        return types.SimpleNamespace(first_name="Kamoliddin", last_name=None,
                                     username="kamolbeek", id=1)

    def disconnect(self) -> None:
        return None


@pytest.fixture
def fake_telethon(monkeypatch):
    """`telethon` moduli o'rniga soxtasini qo'yadi."""
    errors = types.ModuleType("telethon.errors")
    errors.SessionPasswordNeededError = _SessionPasswordNeededError
    errors.PhoneCodeInvalidError = _PhoneCodeInvalidError
    errors.PhoneCodeEmptyError = _PhoneCodeEmptyError
    errors.PhoneCodeExpiredError = _PhoneCodeExpiredError
    errors.PasswordHashInvalidError = _PasswordHashInvalidError
    errors.FloodWaitError = _FloodWaitError

    telethon = types.ModuleType("telethon")
    telethon.errors = errors
    telethon.TelegramClient = _FakeTelegramClient

    monkeypatch.setitem(sys.modules, "telethon", telethon)
    monkeypatch.setitem(sys.modules, "telethon.errors", errors)
    return telethon


@pytest.fixture
def wired(monkeypatch, tmp_path, fake_telethon):
    """Login oqimini soxta mijoz va yozib olinadigan savollar bilan bog'laydi."""
    from jarvis import telegramlogin
    from jarvis.tools import telegram_user as tg

    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setattr(tg, "SESSION_PATH", tmp_path / "telegram.session")
    monkeypatch.setattr(tg, "CREDENTIALS_PATH", tmp_path / "telegram.json")
    monkeypatch.setattr(tg, "STATE_DIR", tmp_path)

    state: dict = {"asked": []}

    def wire(client, answers: list[str]) -> None:
        monkeypatch.setattr(tg, "new_client", lambda *a, **k: client)
        replies = iter(answers)

        def ask(prompt: str, secret: bool = False) -> str:
            state["asked"].append(prompt)
            return next(replies)

        monkeypatch.setattr(telegramlogin, "_ask", ask)

    state["wire"] = wire
    state["login"] = telegramlogin._login
    return state


# --- Testlar -----------------------------------------------------------------


async def test_wrong_code_is_asked_again(wired):
    client = _FakeTelegramClient(codes={"11111": None})
    wired["wire"](client, ["+998901234567", "99999", "11111"])

    assert await wired["login"]() == 0
    assert client.signed_in is True
    # Kod ikki marta so'raldi, yangi kod so'ralmadi (eskisi hali yaroqli).
    assert sum("kod" in p.lower() for p in wired["asked"]) == 2
    assert client.code_requests == 1


async def test_expired_code_triggers_a_new_one(wired):
    client = _FakeTelegramClient(codes={"11111": _PhoneCodeExpiredError(), "22222": None})
    wired["wire"](client, ["+998901234567", "11111", "22222"])

    assert await wired["login"]() == 0
    assert client.signed_in is True
    # Birinchisi + muddati o'tgandan keyin yuborilgani.
    assert client.code_requests == 2


async def test_three_wrong_codes_give_up(wired):
    client = _FakeTelegramClient(codes={})
    wired["wire"](client, ["+998901234567", "1", "2", "3"])

    assert await wired["login"]() == 1
    assert client.signed_in is False


async def test_two_step_password_is_requested(wired):
    client = _FakeTelegramClient(codes={"11111": _SessionPasswordNeededError()},
                                 password="maxfiy")
    wired["wire"](client, ["+998901234567", "11111", "maxfiy"])

    assert await wired["login"]() == 0
    assert client.signed_in is True
    assert any("parol" in p.lower() for p in wired["asked"])
