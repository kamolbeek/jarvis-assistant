"""Uzluksiz suhbat sikli.

Yadroni to'liq qurish uchun mikrofon va API kalitlari kerak bo'ladi, lekin
sikl mantig'i ularga bog'liq emas — shuning uchun `Jarvis` nusxasini
konstruktorsiz yaratib, faqat siklga kerak bo'lgan qismlarni qo'yamiz.
Shu yo'l bilan test aynan haqiqiy `_converse`ni tekshiradi.
"""

from __future__ import annotations

import asyncio

import pytest

from jarvis.app import Jarvis
from jarvis.bus import EventBus, State


class FakeTalker:
    """`_converse` uchun kerakli minimal muhit."""

    def __init__(self, heard: list[str], **talk: object) -> None:
        self.jarvis = Jarvis.__new__(Jarvis)
        self.jarvis.bus = EventBus()
        self.jarvis._shutdown = asyncio.Event()
        self.jarvis._interrupted = False
        self.jarvis._talk = talk

        self.heard = list(heard)
        self.handled: list[str] = []
        self.spoken: list[str] = []
        self.patience: list[float] = []

        self.jarvis._capture_utterance = self._capture  # type: ignore[method-assign]
        self.jarvis._handle_utterance = self._handle    # type: ignore[method-assign]
        self.jarvis._speak = self._speak                # type: ignore[method-assign]

    async def _capture(self, patience_sec: float = 6.0) -> str:
        self.patience.append(patience_sec)
        self.jarvis._interrupted = False
        return self.heard.pop(0) if self.heard else ""

    async def _handle(self, text: str, remote: str | None = None) -> None:
        self.handled.append(text)

    async def _speak(self, text: str, remote: str | None = None) -> None:
        self.spoken.append(text)

    async def run(self) -> None:
        await self.jarvis._converse()


@pytest.mark.asyncio
async def test_follow_up_needs_no_wake_word():
    """Uch marta gapirilsa, uchtasi ham bitta suhbatda ishlanishi kerak."""
    talker = FakeTalker(["birinchi", "ikkinchi", "uchinchi"])

    await talker.run()

    assert talker.handled == ["birinchi", "ikkinchi", "uchinchi"]


@pytest.mark.asyncio
async def test_silence_ends_the_conversation_quietly():
    """Javobdan keyingi jimlik — suhbat tugadi, hech nima deyilmaydi."""
    talker = FakeTalker(["savol"])

    await talker.run()

    assert talker.handled == ["savol"]
    assert talker.spoken == [], "jim ketish uchun ovoz chiqarish kerak emas"
    assert talker.jarvis.bus.state is State.IDLE


@pytest.mark.asyncio
async def test_silence_on_the_first_turn_says_so():
    """Uyg'otib, keyin hech nima aytmaslik — bu boshqa gap, aytib qo'yamiz."""
    talker = FakeTalker([])

    await talker.run()

    assert talker.handled == []
    assert len(talker.spoken) == 1


@pytest.mark.asyncio
async def test_follow_up_can_be_turned_off():
    """`follow_up: false` — har bir savol uchun qaytadan uyg'otish kerak."""
    talker = FakeTalker(["birinchi", "ikkinchi"], follow_up=False)

    await talker.run()

    assert talker.handled == ["birinchi"]


@pytest.mark.asyncio
async def test_max_turns_stops_an_endless_conversation():
    talker = FakeTalker(["gap"] * 10, max_turns=3)

    await talker.run()

    assert talker.handled == ["gap"] * 3


@pytest.mark.asyncio
async def test_first_wait_is_longer_than_the_follow_up_window():
    """Uyg'otgandan keyin o'ylanish mumkin; javobdan keyin oyna qisqaroq."""
    talker = FakeTalker(["savol"], first_wait_sec=6, follow_up_sec=4)

    await talker.run()

    assert talker.patience[0] == 6
    assert talker.patience[1] == 4


@pytest.mark.asyncio
async def test_interrupted_turn_listens_immediately():
    """Gapni bo'lgan odam allaqachon gapirmoqda — uni kutish kerak emas."""
    talker = FakeTalker(["savol", "yo'q, boshqasi"], follow_up_sec=8)

    async def handle(text: str, remote: str | None = None) -> None:
        talker.handled.append(text)
        talker.jarvis._interrupted = True

    talker.jarvis._handle_utterance = handle  # type: ignore[method-assign]
    await talker.run()

    assert talker.handled == ["savol", "yo'q, boshqasi"]
    assert talker.patience[1] < talker.patience[0]


@pytest.mark.asyncio
async def test_shutdown_breaks_the_loop():
    talker = FakeTalker(["gap"] * 5)
    talker.jarvis._shutdown.set()

    await talker.run()

    assert talker.handled == []
