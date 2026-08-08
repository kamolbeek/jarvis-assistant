"""Bo'g'inlar tirikligi reyestri testlari."""

from __future__ import annotations

import asyncio

import pytest

from jarvis.health import AFTERGLOW, Health, Status, System


def collector() -> tuple[list[dict], Health]:
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    return events, Health(emit)


@pytest.mark.asyncio
async def test_snapshot_lists_every_system():
    _, health = collector()
    systems = health.snapshot()["systems"]

    assert len(systems) == len(System)
    assert all(s["status"] == "unknown" for s in systems)
    # Har bir siferblat HUD'da yozuvsiz qolmasin
    assert all(s["label"] for s in systems)


@pytest.mark.asyncio
async def test_busy_marks_active_then_ready():
    events, health = collector()

    async with health.busy(System.STT):
        assert health.status_of(System.STT) is Status.ACTIVE

    assert health.status_of(System.STT) is Status.READY
    assert len(events) == 2


@pytest.mark.asyncio
async def test_busy_marks_down_and_reraises():
    """Xato yuqoriga o'tishi kerak — holat belgilash mantiqni o'zgartirmaydi."""
    _, health = collector()

    with pytest.raises(RuntimeError, match="kalit yo'q"):
        async with health.busy(System.TTS):
            raise RuntimeError("kalit yo'q")

    assert health.status_of(System.TTS) is Status.DOWN
    assert "kalit yo'q" in health._readings[System.TTS].detail


@pytest.mark.asyncio
async def test_cancellation_is_not_a_fault():
    """Jarvis ishni o'zi to'xtatgani nosozlik emas."""
    _, health = collector()

    with pytest.raises(asyncio.CancelledError):
        async with health.busy(System.BRAIN):
            raise asyncio.CancelledError()

    assert health.status_of(System.BRAIN) is Status.READY


@pytest.mark.asyncio
async def test_unchanged_status_does_not_spam_ui():
    events, health = collector()

    await health.mark(System.NET, Status.READY)
    await health.mark(System.NET, Status.READY)
    await health.mark(System.NET, Status.READY)

    assert len(events) == 1, "o'zgarish bo'lmasa xabar ketmasligi kerak"


@pytest.mark.asyncio
async def test_detail_change_reaches_ui():
    """Holat o'sha, sabab boshqa — buni ko'rsatish kerak."""
    events, health = collector()

    await health.mark(System.STT, Status.DOWN, "401 kalit noto'g'ri")
    await health.mark(System.STT, Status.DOWN, "tarmoq yo'q")

    assert len(events) == 2


@pytest.mark.asyncio
async def test_ping_flashes_then_fades(monkeypatch: pytest.MonkeyPatch):
    """Bir zumlik hodisa siferblatni abadiy yoqib qo'ymasligi kerak."""
    _, health = collector()
    now = 1000.0
    monkeypatch.setattr("jarvis.health.time.monotonic", lambda: now)

    await health.ping(System.MIC)
    assert health.status_of(System.MIC) is Status.READY
    assert health._readings[System.MIC].heat(now) == pytest.approx(1.0)

    now += AFTERGLOW / 2
    assert health._readings[System.MIC].heat(now) == pytest.approx(0.5)

    now += AFTERGLOW
    assert health._readings[System.MIC].heat(now) == 0.0


@pytest.mark.asyncio
async def test_ping_does_not_revive_broken_system():
    """Qizil siferblat chaqnashdan yashil bo'lib qolmasligi kerak."""
    _, health = collector()

    await health.mark(System.MIC, Status.DOWN, "ruxsat yo'q")
    await health.ping(System.MIC)

    assert health.status_of(System.MIC) is Status.DOWN


@pytest.mark.asyncio
async def test_troubled_lists_only_problems():
    _, health = collector()

    await health.mark(System.STT, Status.DOWN, "kalit yo'q")
    await health.mark(System.MIC, Status.WARN, "daraja past")
    await health.mark(System.TTS, Status.READY)

    troubled = {r.system for r in health.troubled()}
    assert troubled == {System.STT, System.MIC}


@pytest.mark.asyncio
async def test_emitter_failure_does_not_break_marking():
    """UI uzilgan bo'lsa ham yadro ishlashda davom etsin."""

    async def broken(_event: dict) -> None:
        raise ConnectionError("aloqa yo'q")

    health = Health(broken)
    await health.mark(System.BRAIN, Status.READY)

    assert health.status_of(System.BRAIN) is Status.READY
