"""ElevenLabs ovozini tanlash testlari.

Har bir hisobdagi ovoz to'plami boshqacha bo'ladi, shuning uchun sozlamadagi
nom topilmasligi odatiy hol — Jarvis butunlay ovozsiz qolmasligi kerak.
"""

from __future__ import annotations

import httpx
import pytest

from jarvis.voice.tts import ElevenLabsTts


def _provider_with_voices(monkeypatch: pytest.MonkeyPatch, voices: list[dict],
                          want: str = "Rachel") -> ElevenLabsTts:
    tts = ElevenLabsTts(voice=want)

    async def fake_get(url: str, **kwargs):
        return httpx.Response(200, json={"voices": voices},
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(tts._client, "get", fake_get)
    return tts


@pytest.mark.asyncio
async def test_exact_name_wins(monkeypatch: pytest.MonkeyPatch):
    tts = _provider_with_voices(monkeypatch, [
        {"name": "Aria", "voice_id": "aaaaaaaaaaaaaaaaaaaa"},
        {"name": "Rachel", "voice_id": "rrrrrrrrrrrrrrrrrrrr"},
    ])

    assert await tts._resolve_voice_id("k") == "rrrrrrrrrrrrrrrrrrrr"


@pytest.mark.asyncio
async def test_name_match_is_case_insensitive(monkeypatch: pytest.MonkeyPatch):
    tts = _provider_with_voices(monkeypatch,
                                [{"name": "RACHEL", "voice_id": "rrrrrrrrrrrrrrrrrrrr"}])

    assert await tts._resolve_voice_id("k") == "rrrrrrrrrrrrrrrrrrrr"


@pytest.mark.asyncio
async def test_missing_voice_falls_back_instead_of_failing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """So'ralgan ovoz yo'q — ovozsiz qolgandan ko'ra birinchisiga o'tamiz."""
    tts = _provider_with_voices(monkeypatch, [
        {"name": "Aria", "voice_id": "aaaaaaaaaaaaaaaaaaaa"},
        {"name": "Bill", "voice_id": "bbbbbbbbbbbbbbbbbbbb"},
    ])

    with caplog.at_level("WARNING"):
        assert await tts._resolve_voice_id("k") == "aaaaaaaaaaaaaaaaaaaa"

    # Ogohlantirish qaysi ovoz ishlatilganini va tanlovni aytishi kerak
    assert "Aria" in caplog.text
    assert "Bill" in caplog.text


@pytest.mark.asyncio
async def test_empty_account_explains_what_to_do(monkeypatch: pytest.MonkeyPatch):
    tts = _provider_with_voices(monkeypatch, [])

    with pytest.raises(RuntimeError, match="ovoz yo'q"):
        await tts._resolve_voice_id("k")


@pytest.mark.asyncio
async def test_voice_id_skips_the_lookup(monkeypatch: pytest.MonkeyPatch):
    """20 belgili ID berilgan bo'lsa, ro'yxatni so'rash keraksiz."""
    tts = ElevenLabsTts(voice="21m00Tcm4TlvDq8ikWAM")

    async def explode(*a, **k):
        raise AssertionError("ro'yxat so'ralmasligi kerak edi")

    monkeypatch.setattr(tts._client, "get", explode)

    assert await tts._resolve_voice_id("k") == "21m00Tcm4TlvDq8ikWAM"
