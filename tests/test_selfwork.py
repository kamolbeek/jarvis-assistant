"""O'z ustida ishlash: kamchiliklar daftari, darvoza va ko'rinadigan belgi.

Bu yerda sinaladigan narsa oddiy ko'rinadi, lekin aynan shu uchtasi
«o'zini o'zi yaxshilash» ni xavfli qilmaydigan narsa:

    - kamchilik yo'qolmaydi va takrorlangani ko'rinadi
    - o'chirish kabi amallar HAR SAFAR so'raladi
    - o'z kodiga yozish faqat ruxsat berilganda ochiladi
"""

from __future__ import annotations

import tempfile

import pytest

from jarvis import selfwork
from jarvis.bus import EventBus
from jarvis.config import REPO_ROOT, Config
from jarvis.safety.gate import SafetyGate


@pytest.fixture
def journal(tmp_path, monkeypatch):
    path = tmp_path / "improvements.jsonl"
    monkeypatch.setattr(selfwork, "JOURNAL_PATH", path)
    return path


# --- Kamchiliklar daftari -----------------------------------------------------


def test_note_and_read_back(journal):
    selfwork.note("shikoyat", "juda sekin javob beryapti")
    rows = selfwork.open_issues()

    assert len(rows) == 1
    assert rows[0]["matn"] == "juda sekin javob beryapti"
    assert rows[0]["turi"] == "shikoyat"


def test_repeated_issue_is_counted_not_duplicated(journal):
    """Bir xil xato o'n marta yozilsa ham ro'yxatda bitta bo'lib turadi.

    Aks holda daftar bitta takrorlanuvchi xato bilan to'lib ketadi va
    qolgan kamchiliklar ko'rinmay qoladi.
    """
    for _ in range(3):
        selfwork.note("xato", "TimeoutError: STT javob bermadi")

    rows = selfwork.open_issues()
    assert len(rows) == 1
    assert rows[0]["marta"] == 3


def test_closed_issue_disappears(journal):
    selfwork.note("shikoyat", "orb juda katta")
    assert selfwork.close_issue("orb juda katta") is True
    assert selfwork.open_issues() == []


def test_close_issue_matches_partial_text(journal):
    """Ovozda aytilgan gap daftardagi yozuvga aynan mos kelmaydi."""
    selfwork.note("shikoyat", "javobdan keyin uzoq kutib qoladi")
    assert selfwork.close_issue("uzoq kutib") is True


def test_close_unknown_issue_reports_failure(journal):
    assert selfwork.close_issue("umuman boshqa narsa") is False


def test_note_survives_unwritable_journal(tmp_path, monkeypatch):
    """Daftarga yozib bo'lmasa ham Jarvis to'xtamasligi kerak.

    Papka o'rnida fayl turibdi — bu haqiqiy hayotda ham uchraydi. Kamchilik
    yozuvi tufayli butun javob yiqilsa, "o'zini yaxshilash" ning o'zi yangi
    kamchilikka aylanardi.
    """
    blocker = tmp_path / "blocker"
    blocker.write_text("men papka emasman", encoding="utf-8")
    monkeypatch.setattr(selfwork, "JOURNAL_PATH", blocker / "ichida" / "j.jsonl")

    selfwork.note("xato", "bu yozilmaydi")  # ko'tarilmasligi kerak
    assert selfwork.open_issues() == []


def test_journal_ignores_broken_lines(journal):
    journal.write_text('{"buzuq\n{"ts": "1", "kind": "xato", "text": "haqiqiy"}\n',
                       encoding="utf-8")
    rows = selfwork.open_issues()
    assert [r["matn"] for r in rows] == ["haqiqiy"]


# --- Qayta ishga tushirish ----------------------------------------------------


def test_restart_command_runs_the_module_again():
    command = selfwork.restart_command()
    assert command[1:3] == ["-m", "jarvis"]


async def test_schedule_restart_does_not_block(monkeypatch):
    """Rejalashtirish darhol qaytishi kerak.

    Aks holda model javobi yetib bormaydi va foydalanuvchi nima uchun
    jimlik cho'kkanini bilmay qoladi.
    """
    import asyncio

    calls: list[float] = []

    class FakeLoop:
        def call_later(self, delay, callback):
            calls.append(delay)

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: FakeLoop())
    selfwork.schedule_restart(3.0)

    assert calls == [3.0]


# --- Darvoza: har safar so'raladigan amallar ----------------------------------


def _gate(tmp: str, **safety) -> SafetyGate:
    data = {
        "brain": {"workspace": f"{tmp}/ws"},
        "memory": {"path": f"{tmp}/m.db"},
        "safety": {
            "default": "ask",
            "rules": {"Read": "allow"},
            "writable_roots": [f"{tmp}/ws"],
            "audit_log": f"{tmp}/audit.log",
            **safety,
        },
    }
    cfg = Config(data=data)
    cfg.ensure_dirs()
    return SafetyGate(config=cfg, bus=EventBus())


def _auto_answer(gate: SafetyGate, approved: bool, counter: list[int]):
    async def responder(event: dict) -> None:
        if event.get("type") == "confirm":
            counter.append(1)
            gate.bus.resolve_confirm(event["id"], approved)

    gate.bus.subscribe(responder)


async def test_always_ask_repeats_the_question():
    """«Ha» degani keyingi o'chirishga o'tmaydi.

    Oddiy amallarda seans ruxsati qulay, o'chirishda esa xavfli: bir marta
    tasdiqlangan «kanalni o'chir» keyingisini jimgina o'tkazib yuborardi.
    """
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp, always_ask=["mcp__jarvis__tg_delete_chat"])
        asked: list[int] = []
        _auto_answer(gate, True, asked)

        for _ in range(2):
            decision = await gate.evaluate(
                "mcp__jarvis__tg_delete_chat", {"qayerda": "Eski kanal"}
            )
            assert decision.allowed is True

        assert len(asked) == 2


async def test_always_ask_overrides_allow_rule():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(
            tmp,
            rules={"mcp__jarvis__tg_delete_chat": "allow"},
            always_ask=["mcp__jarvis__tg_delete_chat"],
        )
        asked: list[int] = []
        _auto_answer(gate, True, asked)

        decision = await gate.evaluate("mcp__jarvis__tg_delete_chat", {"qayerda": "K"})

        assert decision.allowed is True
        assert len(asked) == 1, "«allow» bo'lsa ham so'ralishi kerak edi"


async def test_ordinary_telegram_action_passes_without_asking():
    """Kundalik amallar so'ramasdan o'tadi — yordamchi tugmaga aylanmasin."""
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp, rules={"mcp__jarvis__tg_send": "allow"})
        decision = await gate.evaluate("mcp__jarvis__tg_send", {"matn": "salom"})
        assert decision.allowed is True
        assert decision.asked is False


async def test_deny_still_wins_over_always_ask():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(
            tmp,
            rules={"mcp__jarvis__tg_delete_chat": "deny"},
            always_ask=["mcp__jarvis__tg_delete_chat"],
        )
        decision = await gate.evaluate("mcp__jarvis__tg_delete_chat", {"qayerda": "K"})
        assert decision.allowed is False
        assert decision.asked is False


# --- O'z kodiga yozish ruxsati ------------------------------------------------


def test_self_edit_opens_the_repo_for_writing():
    cfg = Config(data={"brain": {"workspace": "~/ws"}, "safety": {"self_edit": True}})
    assert REPO_ROOT in cfg.writable_roots()


def test_repo_is_closed_without_self_edit():
    cfg = Config(data={"brain": {"workspace": "~/ws"}, "safety": {"self_edit": False}})
    assert REPO_ROOT not in cfg.writable_roots()


async def test_gate_blocks_own_code_when_self_edit_is_off():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp)
        decision = await gate.evaluate(
            "Write", {"file_path": str(REPO_ROOT / "jarvis" / "app.py")}
        )
        assert decision.allowed is False


# --- Ko'rinadigan belgi -------------------------------------------------------


async def test_work_badge_is_announced_and_remembered():
    """Yozuv ikkita joyga borishi kerak: hodisa sifatida orbga va shina
    holatiga — keyin ulangan oyna ham uni ko'rsin."""
    bus = EventBus()
    seen: list[dict] = []

    async def collect(event: dict) -> None:
        seen.append(event)

    bus.subscribe(collect)

    await bus.work("O'z ustida ishlamoqda — javob tezligi")

    assert bus.working.startswith("O'z ustida ishlamoqda")
    assert seen[-1] == {
        "type": "work", "active": True,
        "text": "O'z ustida ishlamoqda — javob tezligi",
    }

    await bus.work("")
    assert bus.working == ""
    assert seen[-1]["active"] is False
