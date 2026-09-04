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


class _PhoneNumberInvalidError(_Err):
    pass


class _FloodWaitError(_Err):
    def __init__(self, seconds: int = 60) -> None:
        super().__init__("flood")
        self.seconds = seconds


class _FakeTelegramClient:
    """Skript bo'yicha javob beradigan mijoz."""

    def __init__(self, codes: dict[str, object], password: str = "",
                 bad_phones: tuple[str, ...] = ()) -> None:
        self.codes = codes           # kiritilgan kod -> None (o'tadi) yoki xato
        self.password = password
        self.bad_phones = bad_phones
        self.phones: list[str] = []
        self.code_requests = 0
        self.signed_in = False

    async def connect(self) -> None:
        pass

    async def is_user_authorized(self) -> bool:
        return False

    async def send_code_request(self, phone: str) -> None:
        self.phones.append(phone)
        if phone in self.bad_phones:
            raise _PhoneNumberInvalidError()
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
    errors.PhoneNumberInvalidError = _PhoneNumberInvalidError
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


# --- Telefon raqami ----------------------------------------------------------


@pytest.mark.parametrize("raw", [
    "+998935991333",
    "935991333",              # mamlakat kodisiz — eng ko'p uchraydigan holat
    "998935991333",
    "00998935991333",
    "+998 93 599 13 33",
    "93-599-13-33",
    "(93) 599 13 33",
])
def test_phone_is_normalized(raw: str):
    from jarvis.telegramlogin import normalize_phone, phone_looks_valid

    phone = normalize_phone(raw)
    assert phone == "+998935991333", raw
    assert phone_looks_valid(phone)


@pytest.mark.parametrize("raw", ["", "salom", "12345", "+", "9359913"])
def test_broken_phone_is_rejected(raw: str):
    from jarvis.telegramlogin import normalize_phone, phone_looks_valid

    assert not phone_looks_valid(normalize_phone(raw))


async def test_local_number_reaches_telegram_in_international_form(wired):
    """«935991333» deb yozilsa ham Telegramga «+998935991333» boradi."""
    client = _FakeTelegramClient(codes={"11111": None})
    wired["wire"](client, ["935991333", "11111"])

    assert await wired["login"]() == 0
    assert client.phones == ["+998935991333"]


async def test_unusable_phone_is_asked_again(wired):
    """Tushunarsiz raqamda buyruq to'xtamaydi — qaytadan so'raydi."""
    client = _FakeTelegramClient(codes={"11111": None})
    wired["wire"](client, ["salom", "+998935991333", "11111"])

    assert await wired["login"]() == 0
    assert client.phones == ["+998935991333"]


async def test_phone_rejected_by_telegram_is_asked_again(wired):
    client = _FakeTelegramClient(codes={"11111": None}, bad_phones=("+998900000000",))
    wired["wire"](client, ["+998900000000", "+998935991333", "11111"])

    assert await wired["login"]() == 0
    assert client.phones == ["+998900000000", "+998935991333"]


# --- api_id / api_hash -------------------------------------------------------


def _answers(monkeypatch, values: list[str]) -> list[str]:
    from jarvis import telegramlogin

    asked: list[str] = []
    replies = iter(values)

    def ask(prompt: str, secret: bool = False) -> str:
        asked.append(prompt)
        return next(replies)

    monkeypatch.setattr(telegramlogin, "_ask", ask)
    return asked


def test_api_id_ignores_spaces(monkeypatch):
    from jarvis.telegramlogin import _ask_api_id

    _answers(monkeypatch, ["3478 7018"])
    assert _ask_api_id() == 34787018


def test_api_id_is_asked_again_when_wrong(monkeypatch):
    from jarvis.telegramlogin import _ask_api_id

    asked = _answers(monkeypatch, ["salom", "34787018"])
    assert _ask_api_id() == 34787018
    assert len(asked) == 2


def test_api_hash_accepts_32_hex(monkeypatch):
    from jarvis.telegramlogin import _ask_api_hash

    value = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    _answers(monkeypatch, [value])
    assert _ask_api_hash() == value


def test_empty_api_hash_is_asked_again(monkeypatch):
    """Cmd+V ishlamay qolsa, buyruq to'xtab qolmasin."""
    from jarvis.telegramlogin import _ask_api_hash

    value = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    asked = _answers(monkeypatch, ["", value])
    assert _ask_api_hash() == value
    assert len(asked) == 2


def test_api_hash_gives_up_after_three_tries(monkeypatch):
    from jarvis.telegramlogin import _ask_api_hash

    _answers(monkeypatch, ["", "", "qisqa"])
    assert _ask_api_hash() is None


async def test_keys_are_saved_before_the_phone_step(monkeypatch, wired):
    """Raqam yoki kod xato ketsa ham, kalitlarni qaytadan yozish shart emas."""
    from jarvis.tools import telegram_user as tg

    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)

    api_hash = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    client = _FakeTelegramClient(codes={}, bad_phones=("+998900000000",))
    # Kalitlar to'g'ri, lekin raqam uch marta rad etiladi.
    wired["wire"](client, ["34787018", api_hash,
                           "+998900000000", "+998900000000", "+998900000000"])

    assert await wired["login"]() == 1
    assert tg.CREDENTIALS_PATH.exists()
    assert tg.load_credentials() == (34787018, api_hash)
