"""ElevenLabs ovozini tanlash testlari.

Har bir hisobdagi ovoz to'plami boshqacha bo'ladi, shuning uchun sozlamadagi
nom topilmasligi odatiy hol — Jarvis butunlay ovozsiz qolmasligi kerak.
"""

from __future__ import annotations

import httpx
import pytest

from jarvis.voice.tts import ElevenLabsTts, build_tts


def _provider_with_voices(monkeypatch: pytest.MonkeyPatch, voices: list[dict],
                          want: str = "Rachel", gender: str = "female") -> ElevenLabsTts:
    tts = ElevenLabsTts(voice=want, gender=gender)

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
    """So'ralgan ovoz yo'q — ovozsiz qolgandan ko'ra mos ovozga o'tamiz."""
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
async def test_fallback_trusts_the_gender_label(monkeypatch: pytest.MonkeyPatch):
    """Yorliq bo'lsa, nom ro'yxatiga qaramasdan shunga ishonamiz."""
    tts = _provider_with_voices(monkeypatch, [
        {"name": "Ravshan", "voice_id": "mmmmmmmmmmmmmmmmmmmm",
         "labels": {"gender": "male"}},
        {"name": "Nigora", "voice_id": "ffffffffffffffffffff",
         "labels": {"gender": "female"}},
    ])

    assert await tts._resolve_voice_id("k") == "ffffffffffffffffffff"


@pytest.mark.asyncio
async def test_fallback_uses_known_names_without_labels(monkeypatch: pytest.MonkeyPatch):
    """Yorliq yo'q — tanish ovoz nomlari bo'yicha ayol ovozini topamiz."""
    tts = _provider_with_voices(monkeypatch, [
        {"name": "Roger", "voice_id": "mmmmmmmmmmmmmmmmmmmm"},
        {"name": "Sarah", "voice_id": "ssssssssssssssssssss"},
    ])

    assert await tts._resolve_voice_id("k") == "ssssssssssssssssssss"


@pytest.mark.asyncio
async def test_fallback_honours_male_preference(monkeypatch: pytest.MonkeyPatch):
    """Sozlama erkak ovozini so'rasa, aksi ham ishlashi kerak."""
    tts = _provider_with_voices(monkeypatch, [
        {"name": "Sarah", "voice_id": "ssssssssssssssssssss"},
        {"name": "Roger", "voice_id": "mmmmmmmmmmmmmmmmmmmm"},
    ], gender="male")

    assert await tts._resolve_voice_id("k") == "mmmmmmmmmmmmmmmmmmmm"


@pytest.mark.asyncio
async def test_unrecognised_voices_still_get_one(monkeypatch: pytest.MonkeyPatch):
    """Notanish nomlar va yorliqsiz ro'yxat — baribir gapirishi kerak."""
    tts = _provider_with_voices(monkeypatch, [
        {"name": "Mening ovozim", "voice_id": "cccccccccccccccccccc"},
    ])

    assert await tts._resolve_voice_id("k") == "cccccccccccccccccccc"


def test_azure_default_is_the_uzbek_female_voice():
    """`gender: female` bilan Azure Sardor emas, Madina bo'lishi kerak."""
    provider = build_tts({"provider": "azure", "gender": "female"})

    assert provider._voice == "uz-UZ-MadinaNeural"


def test_azure_male_preference_still_reachable():
    provider = build_tts({"provider": "azure", "gender": "male"})

    assert provider._voice == "uz-UZ-SardorNeural"


def test_explicit_voice_overrides_the_gender_default():
    """Aniq nom yozilgan bo'lsa, jins sozlamasi unga tegmasligi kerak."""
    provider = build_tts({"provider": "azure", "gender": "female",
                          "voice": "uz-UZ-SardorNeural"})

    assert provider._voice == "uz-UZ-SardorNeural"


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
