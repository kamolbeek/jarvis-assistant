"""Dinamik navbati: ikkita ovoz bir vaqtda gapirmasin.

Bu haqiqiy xatodan kelib chiqqan test. Tasdiq savoli alohida vazifada
boshlanadi (`asyncio.create_task`), ya'ni javob hali aytilib turgan paytga
to'g'ri kelishi mumkin. Qulfsiz ikkala tomon ham `Speaker.play` ni ochadi
va foydalanuvchi bir-birining ustidan gapirayotgan ikki ovozni eshitadi:
biri javobni o'qiydi, ikkinchisi «ha yoki yo'q deb ayting» deydi.
"""

from __future__ import annotations

import asyncio

import numpy as np

from jarvis.app import Jarvis
from jarvis.bus import EventBus, State
from jarvis.health import Health


class _FakeTts:
    sample_rate = 16000

    async def stream(self, text: str):
        # Har bir jumla bir necha bo'lakda keladi — ijro davomiyligi bo'lsin.
        for _ in range(3):
            await asyncio.sleep(0.01)
            yield np.zeros(160, dtype=np.int16)


class _RecordingSpeaker:
    """Ijrolarni yozib boradi va ustma-ust tushganini aniqlaydi."""

    def __init__(self) -> None:
        self.playing = 0
        self.overlaps = 0
        self.plays = 0
        self.speaking = False

    def stop(self) -> None:
        pass

    async def play(self, chunks, sample_rate, on_level=None) -> bool:
        self.plays += 1
        self.playing += 1
        self.speaking = True
        if self.playing > 1:
            self.overlaps += 1
        try:
            async for _ in chunks:
                await asyncio.sleep(0)
            return True
        finally:
            self.playing -= 1
            self.speaking = self.playing > 0


def _jarvis() -> tuple[Jarvis, _RecordingSpeaker, list[dict]]:
    jarvis = Jarvis.__new__(Jarvis)
    jarvis.bus = EventBus()
    jarvis.health = Health(jarvis.bus.emit)
    jarvis.tts = _FakeTts()
    jarvis.speaker = _RecordingSpeaker()
    jarvis._barge_in = None
    jarvis._speech_lock = asyncio.Lock()

    said: list[dict] = []

    async def record(event: dict) -> None:
        if event.get("type") == "say":
            said.append(event)

    jarvis.bus.subscribe(record)
    return jarvis, jarvis.speaker, said


async def test_two_speeches_do_not_overlap():
    """Javob va tasdiq savoli bir vaqtda boshlansa ham, ketma-ket aytiladi."""
    jarvis, speaker, _ = _jarvis()

    await asyncio.gather(
        jarvis._speak("Ovozni yaxshilash uchun bir necha yo'l bor."),
        jarvis._speak("Ha yoki yo'q deb ayting."),
    )

    assert speaker.plays == 2
    assert speaker.overlaps == 0, "ikkita ovoz bir-birining ustidan gapirdi"


async def test_captions_follow_the_voice():
    """Ekrandagi matn aytilayotgan gapga mos kelsin — u ham navbat ichida."""
    jarvis, _, said = _jarvis()

    async def second() -> None:
        # Birinchisi boshlanib ulgursin.
        await asyncio.sleep(0.005)
        await jarvis._speak("Ikkinchi")

    await asyncio.gather(jarvis._speak("Birinchi"), second())

    assert [event["text"] for event in said] == ["Birinchi", "Ikkinchi"]


async def test_chime_waits_for_speech_too():
    """Signal ham navbatda — gapirish ustiga chalinmaydi."""
    jarvis, speaker, _ = _jarvis()

    await asyncio.gather(
        jarvis._speak("Uzun javob"),
        jarvis._play_chime(),
    )

    assert speaker.overlaps == 0


async def test_speaking_state_is_still_announced():
    jarvis, _, _ = _jarvis()
    await jarvis._speak("Salom")
    assert jarvis.bus.state is State.SPEAKING
