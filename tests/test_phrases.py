"""Chaqiruv iborasini tanish.

Bu yerdagi misollarning ko'pi o'ylab topilgan emas — STT haqiqatan shunday
yozadi. «hey jarvis» deganda ElevenLabs «Hai, Jervis» deb qaytargan, shuning
uchun taqqoslash qat'iy bo'lsa, uch xil chaqiruvning bittasi ham ishlamaydi.
"""

from __future__ import annotations

import pytest

from jarvis.audio.phrases import PhraseMatcher, build_matcher, normalize


@pytest.fixture
def matcher() -> PhraseMatcher:
    return PhraseMatcher(["hey jarvis", "hi jarvis", "salom jarvis"])


@pytest.mark.parametrize("text", [
    "hey jarvis",
    "Hey, Jarvis!",
    "Hai, Jervis",          # ElevenLabs aynan shunday qaytargan
    "hi jarvis",
    "Hi Jarvis, qalaysan",
    "salom jarvis",
    "Salom, Jarvis.",
    "Assalomu alaykum Jarvis",
    "salom jervis",
    "SALOM JARVIS",
])
def test_the_three_greetings_are_recognised(matcher: PhraseMatcher, text: str):
    assert matcher.matches(text) is True, text


@pytest.mark.parametrize("text", [
    "",
    "salom",                       # ism yo'q — bu bizga qaratilmagan
    "assalomu alaykum",
    "hey, qara bu yerga",
    "bugun havo yaxshi",
    "servis markazi qayerda",      # «servis» — ismga o'xshamaydi
])
def test_speech_without_the_name_is_ignored(matcher: PhraseMatcher, text: str):
    assert matcher.matches(text) is False, text


def test_the_name_alone_is_not_enough_by_default(matcher: PhraseMatcher):
    """Suhbat orasida ismni aytish uyg'otmasligi kerak."""
    assert matcher.matches("jarvis aytgan edi") is False


def test_bare_name_can_be_allowed_explicitly():
    """Ro'yxatga «jarvis» qo'shilsa, salomlashuv talab qilinmaydi."""
    matcher = PhraseMatcher(["jarvis"])

    assert matcher.matches("jarvis") is True
    assert matcher.matches("jervis, eshityapsanmi") is True
    assert matcher.matches("bugun havo yaxshi") is False


def test_greetings_come_from_the_configured_phrases():
    """Sozlamaga yangi ibora qo'shilsa, boshqa hech qayerni tahrirlash kerak emas."""
    matcher = PhraseMatcher(["qale jarvis"])

    assert matcher.matches("qale jarvis") is True
    assert matcher.greetings == frozenset({"qale"})
    assert matcher.matches("hey jarvis") is False, "ro'yxatda yo'q ibora ishlamasligi kerak"


def test_stricter_ratio_rejects_loose_spellings():
    """`phrase_ratio` ni ko'tarish qat'iyroq qiladi."""
    loose = PhraseMatcher(["salom jarvis"], min_ratio=0.7)
    strict = PhraseMatcher(["salom jarvis"], min_ratio=0.95)

    assert loose.matches("salom jervis") is True
    assert strict.matches("salom jervis") is False, "«jervis» endi ismga o'xshamaydi"
    assert strict.matches("salom jarvis") is True


def test_hai_is_recognised_as_hi_not_hey():
    """«Hai» — STT ning odatiy xatosi; u «hi» ga yaqin, «hey» ga emas."""
    both = PhraseMatcher(["hey jarvis", "hi jarvis"])
    only_hey = PhraseMatcher(["hey jarvis"])

    assert both.matches("Hai, Jervis") is True
    assert only_hey.matches("Hai, Jervis") is False


def test_normalize_drops_punctuation_and_case():
    assert normalize("Hey, Jarvis! 21 marta") == ["hey", "jarvis", "marta"]


def test_build_uses_the_three_defaults():
    matcher = build_matcher({})

    assert matcher is not None
    assert matcher.matches("salom jarvis") is True
    assert matcher.matches("hi jarvis") is True


def test_build_returns_none_when_verification_is_off():
    """`phrases: []` — ikkinchi bosqich butunlay o'chadi."""
    assert build_matcher({"phrases": []}) is None
