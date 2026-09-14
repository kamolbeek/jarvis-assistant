"""Gap tugadimi yoki odam hali o'ylayaptimi?

Jimlik taymeri bitta savolga ikki xil javob bera olmaydi. Shuning uchun
qaror matn bo'yicha qabul qilinadi: nuqta qo'yilgan gap darhol javob
oladi, «...va» yoki «aaa» bilan tugagani esa kutiladi.

Eng muhim xossa — ehtiyotkorlik: shubhali so'zni «tugamagan» deb belgilash
har bir javobga ortiqcha soniyalar qo'shadi, ya'ni xato qimmatga tushadi.
"""

from __future__ import annotations

import pytest

from jarvis.voice.unfinished import looks_unfinished


@pytest.mark.parametrize("text", [
    "instagramga kir va",
    "buni qilib keyin",
    "menga kerak chunki",
    "shuni ochib bilan",
    "aaa",
    "eeee",
    "mmm",
])
def test_open_ending_waits(text: str):
    assert looks_unfinished(text) is True, text


@pytest.mark.parametrize("text", [
    "instagramga kir",
    "bugun nima ishlarim bor",
    "Ibratga yoz juma muborak",
    "to'xta",
    "ha",
])
def test_finished_sentence_answers_immediately(text: str):
    assert looks_unfinished(text) is False, text


@pytest.mark.parametrize("text", [
    "instagramga kir va menga aytib ber.",
    "bu nima?",
    "bo'ldi!",
])
def test_punctuation_ends_it(text: str):
    """STT nuqta qo'ygan bo'lsa, kutishning ma'nosi yo'q."""
    assert looks_unfinished(text) is False, text


def test_empty_text_is_not_a_pause():
    assert looks_unfinished("") is False
    assert looks_unfinished("   ") is False


def test_continuation_word_inside_the_sentence_is_ignored():
    """«va» gap o'rtasida — bu davom emas, oddiy bog'lovchi."""
    assert looks_unfinished("Ibrat va Asadga yoz") is False
