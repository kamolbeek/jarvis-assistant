"""`jarvis wake-test` ning ko'rsatish mantig'i.

Mikrofon va model kerak bo'lmaydigan qismlar: ball qanday rangda va qanday
ustun bilan ko'rsatiladi. Rang bu asbobning asosiy xabari — foydalanuvchi
raqamdan ko'ra rangga qaraydi.
"""

from __future__ import annotations

from jarvis.waketune import AMBER, DIM, GREEN, bar, colour

THRESHOLD = 0.5
CANDIDATE = 0.18


def test_bar_grows_with_the_score():
    assert bar(0.0, 10) == " " * 10
    assert bar(0.5, 10) == "█████     "
    assert bar(1.0, 10) == "█" * 10


def test_bar_clamps_out_of_range_scores():
    """Model 1.0 dan katta ball bermasligi kerak, lekin ustun buzilmasin."""
    assert bar(1.5, 8) == "█" * 8
    assert bar(-0.2, 8) == " " * 8


def test_confident_score_is_green():
    assert colour(0.9, THRESHOLD, CANDIDATE) == GREEN
    assert colour(THRESHOLD, THRESHOLD, CANDIDATE) == GREEN


def test_suspicious_score_is_amber():
    """Chegaradan past, lekin sezilgan — matn bilan tekshiriladi."""
    assert colour(0.25, THRESHOLD, CANDIDATE) == AMBER
    assert colour(CANDIDATE, THRESHOLD, CANDIDATE) == AMBER


def test_unheard_score_is_dim():
    assert colour(0.017, THRESHOLD, CANDIDATE) == DIM
    assert colour(0.0, THRESHOLD, CANDIDATE) == DIM
