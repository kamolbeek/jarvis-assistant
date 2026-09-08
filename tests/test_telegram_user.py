"""Shaxsiy Telegram akkaunt: manzilni aniqlash va tasdiq darvozasi.

Bu yerdagi eng muhim ikki xossa:

  * noto'g'ri odamga yozib yubormaslik — bir nechta chat mos kelsa, Jarvis
    o'zi tanlamaydi;
  * `trust on` bo'lganda ham har bir yuborish uchun tasdiq so'ralishi —
    ketgan xabarni qaytarib bo'lmaydi.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.bus import EventBus
from jarvis.config import Config
from jarvis.safety.gate import SafetyGate
from jarvis.tools import telegram_user as tg


# --- Yordamchi soxta mijoz ---------------------------------------------------


class _AsyncList:
    """`async for` bilan aylanadigan oddiy ro'yxat — Telethon iteratorlari o'rniga."""

    def __init__(self, items: list) -> None:
        self.items = items
        self.limit: int | None = None

    def __call__(self, *args, limit: int | None = None, **kwargs):
        self.limit = limit
        return self

    def __aiter__(self):
        self._it = iter(self.items if self.limit is None else self.items[: self.limit])
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


def _dialog(name: str, unread: int = 0, last: str = "") -> SimpleNamespace:
    message = SimpleNamespace(text=last, date=None, out=False, media=None) if last else None
    return SimpleNamespace(name=name, entity=f"entity:{name}", unread_count=unread, message=message)


class _FakeClient:
    def __init__(self, names: list[str], dialogs: list | None = None) -> None:
        self.iter_dialogs = _AsyncList(dialogs if dialogs is not None
                                       else [_dialog(n) for n in names])
        self.iter_messages = _AsyncList([])
        self.sent: list[tuple[str, str]] = []
        self.edited: list[tuple[str, int, str]] = []
        self.removed: list[tuple[str, list[int], bool]] = []
        self._next_id = 101

    async def get_entity(self, target: str):
        return SimpleNamespace(first_name=target.lstrip("@"), last_name=None, username=None, id=1)

    async def send_message(self, entity, text):
        self.sent.append((entity, text))
        message = SimpleNamespace(id=self._next_id)
        self._next_id += 1
        return message

    async def edit_message(self, entity, message_id, text):
        self.edited.append((entity, message_id, text))

    async def delete_messages(self, entity, ids, revoke=False):
        self.removed.append((entity, list(ids), revoke))


def _wire(monkeypatch, names: list[str]) -> _FakeClient:
    """Soxta mijozni ulaydi va oldingi testdan qolgan xabarni tozalaydi."""
    client = _FakeClient(names)

    async def fake_client():
        return client

    monkeypatch.setattr(tg, "get_client", fake_client)
    monkeypatch.setattr(tg, "_last_sent", None)
    return client


# --- Manzilni aniqlash -------------------------------------------------------


async def test_resolve_finds_by_name():
    client = _FakeClient(["Ibrat", "Alisher Aka", "Ish guruhi"])
    entity, name = await tg.resolve(client, "ibrat")
    assert name == "Ibrat"
    assert entity == "entity:Ibrat"


async def test_resolve_prefers_exact_match_over_partial():
    """«Ali» aniq mos kelsa, «Alisher» bilan chalkashmasin."""
    client = _FakeClient(["Ali", "Alisher", "Alisher Aka"])
    _, name = await tg.resolve(client, "Ali")
    assert name == "Ali"


async def test_resolve_refuses_when_several_match():
    """Ikki odam mos kelsa, o'zi tanlamaydi — bu noto'g'ri odamga yozish demak."""
    client = _FakeClient(["Alisher Aka", "Alisher Ustoz"])
    with pytest.raises(tg.TelegramUserError) as exc:
        await tg.resolve(client, "alisher")
    assert "bir nechta" in str(exc.value)
    assert "Alisher Aka" in str(exc.value)


async def test_resolve_reports_unknown_name():
    client = _FakeClient(["Ibrat"])
    with pytest.raises(tg.TelegramUserError) as exc:
        await tg.resolve(client, "Bekzod")
    assert "topilmadi" in str(exc.value)


async def test_resolve_uses_handle_directly():
    """@username va telefon raqam chatlar ro'yxatidan qidirilmaydi."""
    client = _FakeClient([])
    entity, name = await tg.resolve(client, "@ibrat")
    assert name == "ibrat"
    assert entity is not None


async def test_resolve_maps_self_words_to_saved_messages():
    client = _FakeClient([])
    entity, name = await tg.resolve(client, "o'zim")
    assert entity == "me"
    assert "Saqlangan" in name


def test_looks_like_handle():
    assert tg._looks_like_handle("@ibrat")
    assert tg._looks_like_handle("+998901234567")
    assert tg._looks_like_handle("12345678")
    assert not tg._looks_like_handle("Ibrat")


def test_name_of_falls_back_to_username():
    entity = SimpleNamespace(first_name=None, last_name=None, username="ibrat", id=7)
    assert tg.name_of(entity) == "@ibrat"


# --- Kalitlar ----------------------------------------------------------------


def test_credentials_come_from_env_first(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abc")
    assert tg.load_credentials() == (12345, "abc")


def test_credentials_fall_back_to_file(monkeypatch):
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "telegram.json"
        path.write_text(json.dumps({"api_id": 777, "api_hash": "xyz"}), encoding="utf-8")
        monkeypatch.setattr(tg, "CREDENTIALS_PATH", path)
        assert tg.load_credentials() == (777, "xyz")


def test_missing_credentials_explain_the_next_step(monkeypatch):
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(tg, "CREDENTIALS_PATH", Path(tmp) / "yoq.json")
        with pytest.raises(tg.TelegramUserError) as exc:
            tg.load_credentials()
    assert "my.telegram.org" in str(exc.value)
    assert "telegram-login" in str(exc.value)


# --- Tasdiq darvozasi --------------------------------------------------------


SEND_TOOL = "mcp__jarvis__telegram_send"


def _gate(tmp: str, default: str = "ask") -> SafetyGate:
    cfg = Config(data={
        "brain": {"workspace": f"{tmp}/ws"},
        "memory": {"path": f"{tmp}/m.db"},
        "safety": {
            "default": default,
            "rules": {"Read": "allow"},
            "forbidden_patterns": [],
            "writable_roots": [f"{tmp}/ws"],
            "audit_log": f"{tmp}/audit.log",
        },
    })
    cfg.ensure_dirs()
    return SafetyGate(config=cfg, bus=EventBus())


def _autoapprove(gate: SafetyGate, counter: list[dict]) -> None:
    async def approve(event: dict) -> None:
        if event.get("type") == "confirm":
            counter.append(event)
            gate.bus.resolve_confirm(event["id"], True)

    gate.bus.subscribe(approve)


async def test_send_does_not_ask_in_trust_mode():
    """`trust on` yoqilganda yuborish to'xtatilmaydi.

    Himoya boshqa joyda: chat ko'z oldida ochiladi va xato ketgan xabar
    tahrirlanadi yoki olib tashlanadi.
    """
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp, default="allow")
        asked: list[dict] = []
        _autoapprove(gate, asked)

        decision = await gate.evaluate(SEND_TOOL, {"kimga": "Ibrat", "matn": "Salom"})

        assert decision.allowed is True
        assert decision.asked is False
        assert asked == []


async def test_send_still_asks_when_the_config_says_so():
    """Tasdiqni qaytarmoqchi bo'lgan odam uchun yo'l ochiq qolsin."""
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp, default="allow")
        gate._rules[SEND_TOOL] = "ask"
        asked: list[dict] = []
        _autoapprove(gate, asked)

        decision = await gate.evaluate(SEND_TOOL, {"kimga": "Ibrat", "matn": "Juma muborak"})

        assert decision.allowed is True
        assert decision.asked is True
        # Savolda kim va aynan qanday matn ketishi ko'rinib tursin.
        assert "Ibrat" in asked[0]["action"]
        assert "Juma muborak" in asked[0]["detail"]


async def test_send_can_still_be_denied_by_config():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp)
        gate._rules[SEND_TOOL] = "deny"
        decision = await gate.evaluate(SEND_TOOL, {"kimga": "Ibrat", "matn": "Salom"})
        assert decision.allowed is False
        assert decision.asked is False


# --- Chatlarni o'qish --------------------------------------------------------


async def test_list_chats_shows_unread_first_line(monkeypatch):
    client = _FakeClient([], dialogs=[
        _dialog("Ibrat", unread=2, last="Assalomu alaykum"),
        _dialog("Ish guruhi", unread=0, last="ok"),
    ])

    async def fake_client():
        return client

    monkeypatch.setattr(tg, "get_client", fake_client)
    rows = await tg.list_chats(limit=10)

    assert [r["kim"] for r in rows] == ["Ibrat", "Ish guruhi"]
    assert rows[0]["oqilmagan"] == 2
    assert rows[0]["oxirgi_xabar"] == "Assalomu alaykum"


async def test_list_chats_can_show_only_unread(monkeypatch):
    client = _FakeClient([], dialogs=[
        _dialog("Ibrat", unread=2, last="salom"),
        _dialog("Ish guruhi", unread=0, last="ok"),
    ])

    async def fake_client():
        return client

    monkeypatch.setattr(tg, "get_client", fake_client)
    rows = await tg.list_chats(limit=10, unread_only=True)

    assert [r["kim"] for r in rows] == ["Ibrat"]


async def test_read_chat_returns_oldest_first_and_marks_own_messages(monkeypatch):
    client = _FakeClient(["Ibrat"])
    # Telethon yangisidan eskisiga qaytaradi.
    client.iter_messages = _AsyncList([
        SimpleNamespace(text="Rahmat", date=None, out=True, media=None),
        SimpleNamespace(text="Salom", date=None, out=False, media=None),
    ])

    async def fake_client():
        return client

    monkeypatch.setattr(tg, "get_client", fake_client)
    chat = await tg.read_chat("Ibrat", limit=5)

    assert chat["chat"] == "Ibrat"
    assert [m["matn"] for m in chat["xabarlar"]] == ["Salom", "Rahmat"]
    assert [m["kim"] for m in chat["xabarlar"]] == ["Ibrat", "Siz"]


# --- Yuborish ----------------------------------------------------------------


async def test_send_rejects_empty_text(monkeypatch):
    async def fake_client():  # pragma: no cover — chaqirilmasligi kerak
        raise AssertionError("bo'sh matn uchun ulanmasligi kerak")

    monkeypatch.setattr(tg, "get_client", fake_client)
    with pytest.raises(tg.TelegramUserError):
        await tg.send_as_me("Ibrat", "   ")


async def test_send_goes_to_the_resolved_chat(monkeypatch):
    client = _wire(monkeypatch, ["Ibrat", "Bekzod"])
    name = await tg.send_as_me("ibrat", "Juma muborak", show=False)

    assert name == "Ibrat"
    assert client.sent == [("entity:Ibrat", "Juma muborak")]


async def test_chat_is_opened_before_the_message_lands(monkeypatch):
    """Tartib muhim: xabar ko'rinib turgan chatga tushishi kerak.

    Tasdiq so'ramaymiz, ya'ni yagona ogohlantirish shu — ekranda ochilgan
    chat. U xabardan keyin ochilsa, foydalanuvchi nima ketganini o'z
    vaqtida ko'rmaydi.
    """
    client = _wire(monkeypatch, ["Ibrat"])
    order: list[str] = []

    async def fake_open(entity):
        order.append(f"open:{entity}")
        return True

    monkeypatch.setattr(tg, "open_chat", fake_open)
    original_send = client.send_message

    async def watched_send(entity, text):
        order.append("send")
        return await original_send(entity, text)

    client.send_message = watched_send

    await tg.send_as_me("Ibrat", "Salom")
    assert order == ["open:entity:Ibrat", "send"]


# --- Tuzatish -----------------------------------------------------------------


async def test_last_message_can_be_edited(monkeypatch):
    client = _wire(monkeypatch, ["Ibrat"])
    await tg.send_as_me("Ibrat", "Juma muborak", show=False)

    name = await tg.edit_last("Bayramingiz bilan")

    assert name == "Ibrat"
    assert client.edited == [("entity:Ibrat", 101, "Bayramingiz bilan")]


async def test_last_message_can_be_taken_back(monkeypatch):
    """O'chirish qabul qiluvchida ham bo'lishi kerak (revoke)."""
    client = _wire(monkeypatch, ["Ibrat"])
    await tg.send_as_me("Ibrat", "Xato xabar", show=False)

    name = await tg.undo_last()

    assert name == "Ibrat"
    assert client.removed == [("entity:Ibrat", [101], True)]
    assert tg.last_sent() is None, "olib tashlangandan keyin qaytarish uchun narsa qolmaydi"


async def test_editing_without_a_sent_message_explains_itself(monkeypatch):
    _wire(monkeypatch, ["Ibrat"])

    with pytest.raises(tg.TelegramUserError) as exc:
        await tg.edit_last("nimadir")
    assert "yuborilmagan" in str(exc.value)

    with pytest.raises(tg.TelegramUserError):
        await tg.undo_last()
