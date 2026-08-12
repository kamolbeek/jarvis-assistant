"""Suhbatni yakunlash buyrug'ini tanish.

Bu tekshiruv miyaga bormaydi, shuning uchun xato qimmatga tushadi: noto'g'ri
tanilsa, Jarvis gap o'rtasida jim bo'lib qoladi. Shu sababli qoida
ehtiyotkor — faqat aniq buyruq yakunlaydi.
"""

from __future__ import annotations

import pytest

from jarvis.voice.intents import is_end_of_conversation


@pytest.mark.parametrize("text", [
    "suhbatni yakunla",
    "Suhbatni tugat",
    "bo'ldi, yetadi",
    "bo'ldi bas",
    "xayr",
    "yakunla",
    "hozircha yetadi",
    "keyin gaplashamiz",
    "rahmat, yetadi",
    "o'zingni yop",
    "ekrandan chiq",
])
def test_clear_commands_end_the_conversation(text: str):
    assert is_end_of_conversation(text) is True, text


@pytest.mark.parametrize("text", [
    "",
    "bugun nima ishlarim bor",
    "loyihani tugatdim, endi keyingisiga o'tamiz",
    "bu vazifani yakunlangan deb belgila",
    "xayrli tong",
    "rahmat, endi kalendarni ochib ber",
    "bo'ldimi yoki yo'qmi bilmadim",
])
def test_ordinary_speech_does_not_end_it(text: str):
    assert is_end_of_conversation(text) is False, text


def test_a_command_word_inside_a_long_sentence_is_ignored():
    """«tugat» uzun gap ichida boshqa narsaga tegishli bo'lishi mumkin."""
    assert is_end_of_conversation(
        "iLevel loyihasidagi oxirgi vazifani tugat deb yozib qo'y"
    ) is False


def test_apostrophes_do_not_matter():
    """STT tutuq belgisini har xil yozadi — natija bir xil bo'lishi kerak."""
    assert is_end_of_conversation("bo'ldi bas") is True
    assert is_end_of_conversation("boldi bas") is True
    assert is_end_of_conversation("bo‘ldi bas") is True
