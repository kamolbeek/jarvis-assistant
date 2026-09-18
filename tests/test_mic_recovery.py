"""Mikrofon oqimi o'lib qolsa, yadro qotib qolmasin.

Haqiqiy holat: foydalanuvchi musiqani to'xtatdi va Jarvis to'satdan kar
bo'lib qoldi — na chaqiruv, na orbni bosish, na ⌘⇧J ishladi.

Sababi: macOS audio qurilmani almashtirganda PortAudio oqimi jimgina
to'xtaydi. Na xato, na kadr keladi. `queue.get()` esa abadiy kutadi va u
bilan birga butun asosiy sikl to'xtaydi — shuning uchun tugma ham
ishlamay qoladi.
"""

from __future__ import annotations

import asyncio

import numpy as np

from jarvis.audio.mic import MicStream


def _mic() -> MicStream:
    return MicStream(sample_rate=16000, frame_samples=320)


async def test_silence_does_not_freeze_the_loop(monkeypatch):
    """Kadr kelmasa ham sikl aylanishda davom etsin."""
    mic = _mic()
    monkeypatch.setattr(MicStream, "IDLE_TIMEOUT_SEC", 0.05)

    frames = []
    async for frame in mic.frames():
        frames.append(frame)
        if len(frames) >= 3:
            break

    assert len(frames) == 3
    assert all(frame.size == 320 for frame in frames), "jim kadr ham to'liq o'lchamda"
    assert all(not frame.any() for frame in frames), "jim kadr nolga teng"


async def test_real_frames_are_preferred_over_silence(monkeypatch):
    mic = _mic()
    monkeypatch.setattr(MicStream, "IDLE_TIMEOUT_SEC", 0.5)
    mic._push(np.full(320, 7, dtype=np.int16))

    async for frame in mic.frames():
        assert frame[0] == 7
        break


async def test_stall_is_measurable():
    """Qo'riqchi qaror qabul qilishi uchun «qancha vaqt jim» kerak."""
    mic = _mic()
    assert mic.silent_for == 0.0, "hali ochilmagan oqim uchun 0"

    mic._push(np.zeros(320, dtype=np.int16))
    assert mic.silent_for < 0.5

    await asyncio.sleep(0.15)
    assert mic.silent_for >= 0.1


async def test_restart_reopens_the_stream(monkeypatch):
    """Qayta ochish eskisini yopib, yangisini ochadi."""
    mic = _mic()
    events: list[str] = []

    async def fake_stop() -> None:
        events.append("stop")

    async def fake_start() -> None:
        events.append("start")

    monkeypatch.setattr(mic, "stop", fake_stop)
    monkeypatch.setattr(mic, "start", fake_start)

    assert await mic.restart() is True
    assert events == ["stop", "start"]


async def test_restart_reports_failure_instead_of_raising(monkeypatch):
    """Qayta ochib bo'lmasa, yadro yiqilmasin — foydalanuvchiga aytiladi."""
    mic = _mic()

    async def fake_stop() -> None:
        pass

    async def broken_start() -> None:
        raise OSError("qurilma band")

    monkeypatch.setattr(mic, "stop", fake_stop)
    monkeypatch.setattr(mic, "start", broken_start)

    assert await mic.restart() is False


# --- Gap bo'lingandan keyingi orqaga qarash --------------------------------


async def test_recent_keeps_more_than_the_preroll():
    """Bo'lish paytida 300 ms preroll yetmaydi — uzunroq oyna kerak.

    Bo'lish qarori ~350 ms nutqdan keyin qabul qilinadi, undan keyin ham
    ijroni to'xtatishga vaqt ketadi. Shuning uchun `recent` buferi shu
    oynani qoplashi kerak.
    """
    mic = MicStream(sample_rate=16000, frame_samples=320, preroll_ms=300, recent_ms=1700)

    # 2 soniyalik audio: har kadr o'z raqami bilan belgilangan.
    for index in range(100):
        mic._push(np.full(320, index % 100, dtype=np.int16))

    preroll = mic.take_preroll()
    recent = mic.recent(1200)

    assert preroll.size == 320 * 15, "preroll — atigi 300 ms"
    assert recent.size == 320 * 60, "orqaga qarash — 1200 ms"
    assert recent.size > preroll.size * 3


async def test_recent_does_not_clear_the_buffer():
    """`recent` ni ikki marta o'qish mumkin — u tozalamaydi."""
    mic = MicStream(sample_rate=16000, frame_samples=320, recent_ms=1000)
    for index in range(20):
        mic._push(np.full(320, index, dtype=np.int16))

    first = mic.recent(200)
    second = mic.recent(200)

    assert first.size == second.size
    assert np.array_equal(first, second)


async def test_drain_clears_the_queue_so_audio_is_not_doubled():
    """Bo'lishdan keyin navbat tozalanadi — aks holda audio ikki marta tushardi."""
    mic = MicStream(sample_rate=16000, frame_samples=320, recent_ms=1000)
    for index in range(10):
        mic._push(np.full(320, index, dtype=np.int16))

    assert mic._queue.qsize() == 10
    mic.drain()
    assert mic._queue.qsize() == 0
    assert mic.recent(200).size > 0, "tarix saqlanib qolsin"
