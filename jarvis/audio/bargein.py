"""Jarvis gapirayotganda uni bo'lish (barge-in).

Asosiy qiyinchilik — aks sado. Dinamikdan chiqqan Jarvisning o'z ovozi
mikrofonga qaytadi, VAD esa uni ham "nutq" deb belgilaydi. Shuning uchun
faqat nutq borligini bilish yetarli emas: foydalanuvchi ovozi aks sadodan
**sezilarli baland** bo'lishi kerak.

Chegara qattiq yozilmaydi, o'zi moslashadi. Har bir kadrda "hozir eshitilib
turgan fon" darajasini o'rtalab boramiz — quloqchinda bu deyarli nolga
teng bo'ladi (demak sezgirlik yuqori), baland dinamikda esa o'z-o'zidan
ko'tariladi (demak yolg'on bo'linish bo'lmaydi). Bitta sozlama ikki holatni
ham qoplaydi.
"""

from __future__ import annotations

import logging

import numpy as np

from .mic import frame_level
from .vad import SpeechDetector

log = logging.getLogger("jarvis.audio.bargein")


class BargeInWatcher:
    """Ijro davomida mikrofonni kuzatadi va foydalanuvchi gapirsa `True` beradi.

    Ishlatilishi::

        watcher.reset()
        async for frame in mic.frames():
            if watcher.push(frame):
                speaker.stop()
                break
    """

    def __init__(
        self,
        detector: SpeechDetector,
        frame_ms: int = 20,
        min_speech_ms: int = 350,
        margin: float = 2.0,
        min_level: float = 0.05,
        warmup_ms: int = 300,
    ) -> None:
        self._detector = detector
        self._need = max(1, min_speech_ms // max(1, frame_ms))
        self._warmup = max(1, warmup_ms // max(1, frame_ms))
        self._margin = max(1.1, margin)
        self._min_level = min_level
        self._floor = 0.0
        self._run = 0
        self._seen = 0

    def reset(self) -> None:
        """Yangi gap boshlanishida chaqiriladi."""
        self._floor = 0.0
        self._run = 0
        self._seen = 0

    @property
    def gate(self) -> float:
        """Hozirgi chegara — nima uchun bo'lmaganini tushunish uchun foydali."""
        return max(self._min_level, self._floor * self._margin)

    def push(self, frame: np.ndarray) -> bool:
        level = frame_level(frame)
        self._seen += 1

        # Ijroning boshida fon hali o'lchanmagan — bu paytda o'z ovozimizni
        # foydalanuvchi deb o'ylab qolmaslik uchun tez moslashamiz va
        # hech kimni bo'lmaymiz.
        if self._seen <= self._warmup:
            self._floor = 0.7 * self._floor + 0.3 * level
            return False

        if level > self.gate and self._detector.is_speech(frame):
            self._run += 1
            if self._run >= self._need:
                log.info("Gapni bo'lish: daraja %.2f > chegara %.2f", level, self.gate)
                return True
            return False

        # Bir-ikki tasodifiy kadr hisobni nolga tushirmasin, lekin
        # to'planib ham qolmasin.
        self._run = max(0, self._run - 1)
        self._floor = 0.95 * self._floor + 0.05 * level
        return False


def build_barge_in(cfg: dict, detector: SpeechDetector, frame_ms: int) -> BargeInWatcher | None:
    """Sozlamaga qarab kuzatuvchi yaratadi; o'chirilgan bo'lsa `None`."""
    if not cfg.get("barge_in", True):
        return None
    return BargeInWatcher(
        detector=detector,
        frame_ms=frame_ms,
        min_speech_ms=int(cfg.get("barge_in_min_speech_ms", 350)),
        margin=float(cfg.get("barge_in_margin", 2.0)),
    )
