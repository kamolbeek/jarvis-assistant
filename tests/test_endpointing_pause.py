"""Uzun gapning o'rtasidagi nafas «gap tugadi» deb o'qilmasin.

Haqiqiy holat: foydalanuvchi uzoq gapiradi, o'rtada bir nafas oladi.
900 ms chegara bilan o'sha nafas gapni ikkiga bo'lib yuborardi: birinchi
bo'lagi miyaga ketardi, qolgani esa alohida savol bo'lib kelardi va
boshidagi mazmun yo'qolardi.
"""

from __future__ import annotations

import numpy as np

from jarvis.audio.vad import Endpointer, SpeechDetector

FRAME = 320
FRAME_MS = 20


class _Scripted(SpeechDetector):
    def __init__(self, script: list[bool]) -> None:
        self._script = list(script)
        self._index = 0

    def is_speech(self, frame: np.ndarray) -> bool:
        if self._index < len(self._script):
            value = self._script[self._index]
            self._index += 1
            return value
        return False


def _run(script: list[bool], silence_ms: int) -> Endpointer:
    ep = Endpointer(_Scripted(script), frame_ms=FRAME_MS, silence_ms=silence_ms)
    frame = np.zeros(FRAME, dtype=np.int16)
    for _ in script:
        ep.push(frame)
        if ep.finished:
            break
    return ep


def test_a_breath_in_the_middle_does_not_end_the_sentence():
    """1 soniyalik nafas — gap davom etyapti, tugagani emas."""
    speech = [True] * 50        # 1 s gapirish
    breath = [False] * 50       # 1 s jimlik
    more = [True] * 50          # yana 1 s gapirish

    ep = _run(speech + breath + more, silence_ms=1500)

    assert ep.finished is False, "nafas gapni bo'lib yubordi"


def test_a_real_stop_still_ends_the_sentence():
    speech = [True] * 50
    stop = [False] * 100        # 2 s jimlik — endi haqiqatan tugadi

    ep = _run(speech + stop, silence_ms=1500)

    assert ep.finished is True


def test_the_old_threshold_would_have_split_it():
    """Eski 900 ms nima uchun yaramasligini ko'rsatadi."""
    speech = [True] * 50
    breath = [False] * 50

    ep = _run(speech + breath, silence_ms=900)

    assert ep.finished is True, "900 ms da nafas gap tugadi deb o'qilardi"
