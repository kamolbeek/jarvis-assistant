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


# --- Buzilishni aniqlash -------------------------------------------------------
#
# Amalda ko'rilgan holat: uch o'lchovda ham cho'qqi 1.00 edi, lekin kesilgan
# kadrlar ulushi chegaradan past bo'lgani uchun asbob faqat bittasida
# ogohlantirdi. Cho'qqining o'zi devorga tegib turgani yetarli dalil.


def test_rail_peak_counts_as_distortion_on_its_own():
    from jarvis.waketune import Measurement

    assert Measurement(peak=0.1, loudest=1.00, clipped=0.0).distorted is True
    assert Measurement(peak=0.1, loudest=0.98, clipped=0.0).distorted is True


def test_clean_loud_signal_is_not_distortion():
    """Baland, lekin devorga tegmagan signal — bu normal."""
    from jarvis.waketune import Measurement

    assert Measurement(peak=0.9, loudest=0.75, clipped=0.0).distorted is False


def test_a_few_clipped_frames_are_enough():
    from jarvis.waketune import Measurement

    assert Measurement(peak=0.3, loudest=0.6, clipped=0.004).distorted is True
    assert Measurement(peak=0.3, loudest=0.6, clipped=0.001).distorted is False


# --- Chegara tavsiyasi ---------------------------------------------------------
#
# Haqiqiy o'lchovlar (MacBook Pro mikrofoni, toza signal):
#   hey jarvis 0.485 · hi jarvis 0.427 · salom jarvis 0.012
# Chegara 0.50 edi — ikkita ibora arang o'tmagan. Tavsiya shu holatni
# tuzatishi, lekin shovqin darajasidan pastga tushmasligi kerak.


def test_threshold_lands_below_the_working_phrases():
    from jarvis.waketune import recommend

    advice = recommend(0.05, {"hey jarvis": 0.485, "hi jarvis": 0.427,
                              "salom jarvis": 0.012})

    assert advice["threshold"] < 0.427, "ikkita ibora o'tishi kerak"
    assert advice["threshold"] > 0.08, "shovqin darajasiga tushmasligi kerak"
    assert advice["working"] == ["hey jarvis", "hi jarvis"]
    assert advice["hopeless"] == ["salom jarvis"]


def test_noise_floor_wins_when_it_is_higher():
    """Shovqin balandligi ovoz balidan yuqori chiqsa, chegara shovqinga qarab qo'yiladi.

    Aks holda xonaning o'zi Jarvisni uyg'otib yuboradi. Ovoz bali baland
    bo'lganda esa shovqin ta'sir qilmaydi — chegara baribir undan yuqori.
    """
    from jarvis.waketune import recommend

    quiet = recommend(0.05, {"hey jarvis": 0.85})
    noisy = recommend(0.50, {"hey jarvis": 0.85})

    assert quiet["threshold"] == 0.72, "ovoz baliga qarab qo'yiladi"
    assert noisy["threshold"] == 0.80, "shovqin cheki yuqori — o'sha g'olib"


def test_candidate_always_clears_the_noise():
    """Eng muhim invariant: shubhali chegara shovqindan yuqori bo'lishi shart.

    Aks holda xonadagi shitirlash har safar STT chaqiruvini keltirib chiqaradi.
    """
    from jarvis.waketune import recommend

    for noise in (0.02, 0.10, 0.25, 0.45):
        advice = recommend(noise, {"hey jarvis": 0.95})
        assert advice["candidate"] > noise, f"shovqin {noise}"


def test_phrases_below_the_noise_floor_are_hopeless():
    """Shovqindan past ball — chegara bilan qutqarib bo'lmaydi."""
    from jarvis.waketune import recommend

    advice = recommend(0.30, {"salom jarvis": 0.20})

    assert advice["threshold"] is None
    assert advice["hopeless"] == ["salom jarvis"]


def test_candidate_stays_below_the_threshold():
    """Shubhali chegara asosiysidan past bo'lishi kerak, aks holda ma'nosiz."""
    from jarvis.waketune import recommend

    advice = recommend(0.08, {"hey jarvis": 0.485})

    assert advice["candidate"] < advice["threshold"]
    assert advice["candidate"] >= 0.05
