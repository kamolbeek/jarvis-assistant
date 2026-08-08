"""Uyg'otuvchi so'z aniqlagichining sovish davri va yozuvni tekshirishi.

Bu testlar haqiqiy nosozlikdan keyin yozildi. `wake-test` bir xil iborani
ikki marta o'lchaganda 0.817 va 0.073 ball berdi — bunday tarqalish model
xatosi emas edi: chaqiruv sodir bo'lgach, sovish davri KEYINGI o'lchovga
o'tib ketardi va o'sha o'lchovning boshidagi audio jimgina tashlanardi.
`reset()` sovish davrini tozalamagani sabab bo'lgan.

Model kerak bo'lmasin — ball qaytaradigan soxta backend yetadi.
"""

from __future__ import annotations

import numpy as np

from jarvis.audio.wake import WakeWordDetector

FRAME = 320       # 20 ms @ 16 kHz
CHUNK = 1280      # aniqlagich shuncha namunani kutadi


class ScriptedDetector(WakeWordDetector):
    """Har bir bo'lak uchun oldindan yozilgan ball qaytaradi."""

    def __init__(self, scores: list[float], **kw) -> None:
        super().__init__(CHUNK, sample_rate=16000, **kw)
        self._scores = list(scores)
        self.calls = 0

    @property
    def threshold(self) -> float:
        return 0.5

    def _score(self, chunk: np.ndarray) -> float:
        self.calls += 1
        return self._scores.pop(0) if self._scores else 0.0


def frames(count: int) -> list[np.ndarray]:
    return [np.full(FRAME, 1000, dtype=np.int16) for _ in range(count)]


def feed(detector: WakeWordDetector, count: int) -> list:
    return [hit for f in frames(count) if (hit := detector.push(f)) is not None]


def test_confident_hit_is_reported():
    detector = ScriptedDetector([0.9], candidate_threshold=0.2)

    hits = feed(detector, 4)  # 4 x 320 = 1280 = bitta bo'lak

    assert len(hits) == 1
    assert hits[0].confident is True
    assert hits[0].score == 0.9


def test_candidate_hit_is_not_confident():
    detector = ScriptedDetector([0.3], candidate_threshold=0.2)

    hits = feed(detector, 4)

    assert len(hits) == 1
    assert hits[0].confident is False


def test_score_below_candidate_is_silent():
    detector = ScriptedDetector([0.1], candidate_threshold=0.2)

    assert feed(detector, 4) == []


def test_confident_hit_starts_the_full_cooldown():
    """Uyg'ongandan keyin o'sha iborani ikkinchi marta hisoblamaslik kerak."""
    detector = ScriptedDetector([0.9] + [0.9] * 20, candidate_threshold=0.2,
                                cooldown_sec=2.0)

    first = feed(detector, 4)
    # 2 soniya = 100 kadr; shundan kamrog'i sovish davrida qoladi
    during = feed(detector, 50)

    assert len(first) == 1
    assert during == [], "sovish davrida jim turishi kerak"


def test_candidate_cooldown_is_short():
    """Shubhali chaqiruv tasdiqlanmasligi mumkin — uzoq kar bo'lib turmaymiz."""
    detector = ScriptedDetector([0.3] + [0.3] * 60, candidate_threshold=0.2,
                                cooldown_sec=2.0)

    feed(detector, 4)
    # 0.6 s = 30 kadr. 50 kadrdan keyin yana eshitishi kerak.
    again = feed(detector, 50)

    assert again, "qisqa muddatdan keyin qaytadan eshitishi kerak"


def test_reset_clears_the_cooldown():
    """Aynan shu xato o'lchovlarni chalkashtirgan edi."""
    detector = ScriptedDetector([0.9] + [0.9] * 20, candidate_threshold=0.2,
                                cooldown_sec=2.0)
    feed(detector, 4)

    detector.reset()
    after = feed(detector, 4)

    assert after, "reset()dan keyin darhol eshitishi kerak"


def test_peak_records_scores_below_the_threshold():
    """Sozlash uchun eng muhim raqam — chaqiruvga yetmagan ballning cho'qqisi."""
    detector = ScriptedDetector([0.05, 0.17, 0.09], candidate_threshold=0.5)

    feed(detector, 12)

    assert detector.peak == 0.17

    detector.clear_peak()
    assert detector.peak == 0.0


def test_scan_is_repeatable():
    """Bir xil yozuv har safar bir xil ball berishi kerak.

    Tuzatishdan oldin ikkinchi o'tish oldingi chaqiruvning sovish davriga
    tushib qolar va 0.000 chiqarardi.
    """
    audio = np.full(16000, 1000, dtype=np.int16)

    def once() -> float:
        # Har bir moslashuv uchun bir xil ball beradigan skript
        return ScriptedDetector([0.8] * 400, candidate_threshold=0.2).scan(audio, FRAME)

    assert once() == once() == 0.8


def test_scan_ignores_empty_audio():
    detector = ScriptedDetector([0.9] * 10, candidate_threshold=0.2)

    assert detector.scan(np.zeros(0, dtype=np.int16), FRAME) == 0.0


def test_scan_tries_several_alignments():
    """Jonli oqimda model iborani turli moslashuvda ko'radi — scan ham shunday.

    Bo'lak 1280 namuna, kadr 320 — ya'ni to'rtta siljish bo'lishi kerak.
    """
    detector = ScriptedDetector([0.0] * 2000, candidate_threshold=0.9)
    detector.scan(np.full(16000, 500, dtype=np.int16), FRAME)

    # Har bir siljish butun yozuvni qaytadan o'tkazadi
    assert detector.calls > 4 * 10, "to'rtta moslashuv sinalishi kerak"
