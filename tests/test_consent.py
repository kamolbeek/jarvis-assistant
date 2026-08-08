"""Ovozli tasdiq: so'zlarni o'qish va butun oqim.

Eng muhim xossa — xavfsizlik tomonga og'ish: «ruxsat bermayman» ichida
«ruxsat» so'zi bor, lekin bu RAD. Rad so'zi topilgan har qanday javob rad
deb o'qiladi, noaniq javob esa hech qachon roziliqqa aylanmaydi.
"""

from __future__ import annotations

import asyncio

import pytest

from jarvis.app import Jarvis
from jarvis.bus import EventBus
from jarvis.voice.consent import consent_prompt, parse_consent


# --- So'zlarni o'qish ---------------------------------------------------------

@pytest.mark.parametrize("text", [
    "ha",
    "Ha, ruxsat beraman",
    "mayli",
    "mayli, bajar",
    "davom et",
    "xo'p",
    "hop",
    "albatta",
    "qilaver",
    "boshla",
    "Yaxshi, davom ettir",
])
def test_yes_is_recognised(text: str):
    assert parse_consent(text) is True, text


@pytest.mark.parametrize("text", [
    "yo'q",
    "yoq",
    "Yo'q, to'xta",
    "bekor qil",
    "qilma",
    "to'xta",
    "kerak emas",
    "shart emas",
    "rad etaman",
])
def test_no_is_recognised(text: str):
    assert parse_consent(text) is False, text


def test_no_beats_yes_when_both_present():
    """«ruxsat bermayman»: ichida YES so'zi ham bor — baribir RAD."""
    assert parse_consent("ruxsat bermayman") is False
    assert parse_consent("ha demoqchi edim, lekin yo'q") is False


@pytest.mark.parametrize("text", ["", "bilmadim", "nima edi u", "hmm qiziq"])
def test_unclear_is_never_a_yes(text: str):
    assert parse_consent(text) is None, text


def test_prompt_skips_long_details():
    """Uzun buyruqni ovozda o'qish befoyda — ekranda ko'rinib turibdi."""
    short = consent_prompt("Buyruq bajarilsinmi?", "ls -la")
    long = consent_prompt("Buyruq bajarilsinmi?", "python -c " + "x" * 200)

    assert "ls -la" in short
    assert "xxxx" not in long
    assert "Ha yoki yo'q" in long


# --- Butun oqim ---------------------------------------------------------------

def _jarvis(answers: list[str]) -> tuple[Jarvis, list[str]]:
    """Ovozli tasdiqqa kerak bo'lgan qismlargina tayyorlangan yadro."""
    jarvis = Jarvis.__new__(Jarvis)
    jarvis.bus = EventBus()
    jarvis._shutdown = asyncio.Event()
    jarvis._vc_listen = 1.0
    jarvis._vc_attempts = 2

    class FakeMic:
        def drain(self) -> None: ...

    jarvis.mic = FakeMic()
    spoken: list[str] = []

    async def speak(text: str, remote: str | None = None) -> None:
        spoken.append(text)

    async def capture(patience_sec: float = 6.0) -> str:
        return answers.pop(0) if answers else ""

    jarvis._speak = speak                    # type: ignore[method-assign]
    jarvis._capture_utterance = capture      # type: ignore[method-assign]
    return jarvis, spoken


async def _run_confirm(jarvis: Jarvis, action: str = "Buyruq bajarilsinmi?",
                       detail: str = "ls") -> bool:
    """Haqiqiy `request_confirm` bilan ovozli javobni uchrashtiradi."""
    ask = asyncio.create_task(jarvis.bus.request_confirm(action, detail, timeout=5))
    await asyncio.sleep(0.01)  # so'rov ro'yxatga tushsin

    confirm_id = next(iter(jarvis.bus._pending))
    await jarvis._voice_confirm({"id": confirm_id, "action": action, "detail": detail})
    return await ask


@pytest.mark.asyncio
async def test_spoken_yes_approves():
    jarvis, spoken = _jarvis(["ha, ruxsat beraman"])

    assert await _run_confirm(jarvis) is True
    assert any("Xo'p" in s for s in spoken)


@pytest.mark.asyncio
async def test_spoken_no_denies():
    jarvis, spoken = _jarvis(["yo'q, kerak emas"])

    assert await _run_confirm(jarvis) is False
    assert any("Bekor" in s for s in spoken)


@pytest.mark.asyncio
async def test_unclear_then_yes_reasks_once():
    jarvis, spoken = _jarvis(["bilmadim nima", "mayli, bajar"])

    assert await _run_confirm(jarvis) is True
    assert any("Ha yoki yo'q" in s for s in spoken), "qayta so'rashi kerak"


@pytest.mark.asyncio
async def test_silence_leaves_the_decision_to_the_timeout():
    """Javob bo'lmasa, ovoz oqimi taxmin qilmaydi — muddat RAD deb yakunlaydi."""
    jarvis, _ = _jarvis([])

    ask = asyncio.create_task(jarvis.bus.request_confirm("Amal?", "x", timeout=0.4))
    await asyncio.sleep(0.01)
    confirm_id = next(iter(jarvis.bus._pending))
    await jarvis._voice_confirm({"id": confirm_id, "action": "Amal?", "detail": "x"})

    assert jarvis.bus.is_pending(confirm_id), "ovoz oqimi o'zicha hal qilmasligi kerak"
    assert await ask is False, "muddat tugashi rad deb o'qiladi"


@pytest.mark.asyncio
async def test_button_first_wins_and_voice_stays_silent():
    """Tugma oldin bosilgan bo'lsa, ovoz oqimi indamay chiqib ketadi."""
    jarvis, spoken = _jarvis(["ha"])

    ask = asyncio.create_task(jarvis.bus.request_confirm("Amal?", "x", timeout=5))
    await asyncio.sleep(0.01)
    confirm_id = next(iter(jarvis.bus._pending))
    jarvis.bus.resolve_confirm(confirm_id, False)  # tugma: rad

    await jarvis._voice_confirm({"id": confirm_id, "action": "Amal?", "detail": "x"})

    assert await ask is False
    assert not any("Xo'p" in s for s in spoken), "ovoz keyin kelib gapirmasligi kerak"
