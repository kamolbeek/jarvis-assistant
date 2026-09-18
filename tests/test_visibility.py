"""Ko'rinuvchanlik: Jarvis hozir nima qilayotgani ekranda turishi.

Nima uchun bu alohida sinaladi. Bir marta shunday bo'ldi: foydalanuvchi savol
berdi, Jarvis «labbay» dedi va... jim qoldi. Sababi nutqni matnga aylantirish
yiqilgani edi, lekin xato faqat jurnalga tushgan — ekranda hech nima
o'zgarmagan. Tashqaridan qaraganda yordamchi «uxlab qolgan»dek ko'rinadi va
nima qilish kerakligini bilib bo'lmaydi.

Shuning uchun uchta qat'iy talab:

    1. har bosqichda holat va aniq ish ekranda bo'ladi;
    2. nosozlik ekranda QOLADI — vaqt bo'yicha so'nmaydi;
    3. kech ulangan oyna ham hozirgi holatni darhol oladi.
"""

from __future__ import annotations

import numpy as np
import pytest

from jarvis.bus import EventBus, State
from jarvis.safety.gate import describe_activity
from jarvis.voice.stt import SttProvider, transcribe_guarded


def _collector(bus: EventBus) -> list[dict]:
    seen: list[dict] = []

    async def collect(event: dict) -> None:
        seen.append(event)

    bus.subscribe(collect)
    return seen


# --- Holat qatori -------------------------------------------------------------


async def test_activity_is_published_and_remembered():
    bus = EventBus()
    seen = _collector(bus)

    await bus.activity("Telegram: papka")

    assert bus.activity_text == "Telegram: papka"
    assert seen[-1] == {"type": "activity", "text": "Telegram: papka"}


async def test_new_stage_clears_the_previous_activity():
    """«Telegram: papka» yozuvi gapirish bosqichida ham turib qolmasin."""
    bus = EventBus()
    await bus.activity("Telegram: papka")
    seen = _collector(bus)

    await bus.set_state(State.SPEAKING)

    assert bus.activity_text == ""
    assert {"type": "activity", "text": ""} in seen


async def test_thinking_keeps_the_activity():
    """Asboblar aynan «o'ylayapti» bosqichida chaqiriladi.

    Har chaqiruvda holat qayta o'rnatilsa, asbob nomi darhol o'chib ketardi
    va ekranda hech qachon ko'rinmasdi.
    """
    bus = EventBus()
    await bus.activity("Telegram: o'qiyapti")

    await bus.set_state(State.THINKING)

    assert bus.activity_text == "Telegram: o'qiyapti"


async def test_problem_stays_until_cleared():
    bus = EventBus()
    seen = _collector(bus)

    await bus.problem("Nutqni matnga aylantirib bo'lmadi")
    assert bus.problem_text.startswith("Nutqni")

    await bus.clear_problem()
    assert bus.problem_text == ""
    assert seen[-1] == {"type": "problem", "text": ""}


async def test_clearing_a_missing_problem_is_quiet():
    """Har muvaffaqiyatli qadamda tozalash chaqiriladi — u shovqin qilmasin."""
    bus = EventBus()
    seen = _collector(bus)

    await bus.clear_problem()

    assert seen == []


# --- Asbob nomini o'zbekchalashtirish -----------------------------------------


@pytest.mark.parametrize(
    ("tool", "expected"),
    [
        ("mcp__jarvis__telegram_folder", "Telegram: papka"),
        ("mcp__jarvis__telegram_read", "Telegram: o'qiyapti"),
        ("mcp__jarvis__self_check", "o'z kodi: tekshiryapti"),
        ("Bash", "buyruq bajaryapti"),
        ("WebSearch", "internetdan qidiryapti"),
    ],
)
def test_activity_label_is_readable(tool: str, expected: str):
    assert describe_activity(tool) == expected


def test_dangerous_tools_keep_their_full_name():
    """O'chirish kabi amallar qisqartirilmasin — ular tasdiq savolida chiqadi."""
    assert describe_activity("mcp__jarvis__telegram_delete_chat") == (
        "Telegram chatini o'chirish"
    )


def test_unknown_tool_falls_back_to_its_own_name():
    assert describe_activity("SomeNewTool") == "SomeNewTool"


# --- Nutqni matnga aylantirishdagi jimlik -------------------------------------


class _BrokenStt(SttProvider):
    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        raise RuntimeError("whisper-cli topilmadi")


class _WorkingStt(SttProvider):
    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        return "salom"


def _audio(seconds: float = 1.0, sample_rate: int = 16000) -> np.ndarray:
    return np.zeros(int(seconds * sample_rate), dtype=np.int16)


async def test_stt_failure_reports_a_reason():
    """Jimlikning sababi chaqiruvchiga yetkaziladi, faqat jurnalga emas."""
    reasons: list[str] = []

    async def remember(reason: str) -> None:
        reasons.append(reason)

    text = await transcribe_guarded(_BrokenStt(), _audio(), 16000, on_error=remember)

    assert text == ""
    assert len(reasons) == 1
    assert "whisper-cli topilmadi" in reasons[0]


async def test_stt_success_reports_nothing():
    reasons: list[str] = []

    async def remember(reason: str) -> None:
        reasons.append(reason)

    text = await transcribe_guarded(_WorkingStt(), _audio(), 16000, on_error=remember)

    assert text == "salom"
    assert reasons == []


async def test_too_short_audio_is_not_a_failure():
    """Tasodifiy shitirlash uchun ekranga qizil yozuv chiqmasin."""
    reasons: list[str] = []

    async def remember(reason: str) -> None:
        reasons.append(reason)

    text = await transcribe_guarded(_BrokenStt(), _audio(0.1), 16000, on_error=remember)

    assert text == ""
    assert reasons == []


async def test_stt_works_without_a_reporter():
    """`on_error` berilmasa ham yiqilmasligi kerak — eski chaqiruvlar uchun."""
    assert await transcribe_guarded(_BrokenStt(), _audio(), 16000) == ""
