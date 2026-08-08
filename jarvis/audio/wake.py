"""Uyg'otuvchi so'z ("Hey Jarvis") aniqlagichi.

Ikki backend qo'llab-quvvatlanadi:
  * openwakeword — ochiq kodli, bepul, `hey_jarvis` tayyor modeli bilan keladi (standart);
  * porcupine    — Picovoice, `jarvis` kalit so'zi built-in (bepul tier uchun kalit kerak).

Har ikkalasi ham o'zining kadr o'lchamini talab qiladi, shuning uchun kiruvchi
kadrlarni ichki buferda kerakli o'lchamgacha to'plab beramiz.

Aniqlagich ikki darajali javob beradi. Tayyor model faqat «hey jarvis»ga
o'rgatilgan, «salom jarvis» esa unga faqat qismincha o'xshaydi — natijada
ball chegaradan past chiqadi. Shu sababli past chegaradan o'tgan ovoz
"shubhali" deb belgilanadi: uni tashlab yubormaymiz, matn bilan tekshiramiz
(`phrases.PhraseMatcher`). Chegaraning o'zini pasaytirish yaramaydi —
u holda televizor ovozi ham uyg'otib yuboradi.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

log = logging.getLogger("jarvis.audio.wake")


@dataclass(frozen=True)
class WakeHit:
    """Uyg'otuvchi so'zga o'xshash ovoz eshitildi.

    `confident` — ball asosiy chegaradan o'tdi, darhol uyg'onish mumkin.
    Aks holda bu shubhali chaqiruv: matn bilan tasdiqlash kerak.
    """

    score: float
    confident: bool


class WakeWordDetector(ABC):
    """Umumiy interfeys: kadrni bering, uyg'otuvchi so'z eshitilsa `WakeHit` qaytadi.

    Sovish davri (cooldown) audio namunalari bo'yicha o'lchanadi, real soat
    bo'yicha emas — kadrlar navbatda to'planib qolganda ham xulq bir xil bo'lsin.
    """

    def __init__(self, chunk_samples: int, cooldown_sec: float = 2.0,
                 sample_rate: int = 16000, candidate_threshold: float = 1.0) -> None:
        self._chunk_samples = chunk_samples
        self._cooldown_sec = cooldown_sec
        self._sample_rate = sample_rate
        self._candidate_threshold = candidate_threshold
        self._buffer = np.zeros(0, dtype=np.int16)
        self._clock = 0.0
        self._last_fire = -1e9
        self._peak = 0.0

    @property
    def peak(self) -> float:
        """Oxirgi tozalashdan keyingi eng baland ball — sozlash uchun."""
        return self._peak

    def clear_peak(self) -> None:
        self._peak = 0.0

    def push(self, frame: np.ndarray) -> WakeHit | None:
        now = self._clock
        self._clock += frame.size / self._sample_rate

        if now - self._last_fire < self._cooldown_sec:
            # Sovish davrida buferni to'ldirmaymiz — eskirgan audio bilan ishga tushmasin.
            self._buffer = np.zeros(0, dtype=np.int16)
            return None

        self._buffer = np.concatenate([self._buffer, frame.astype(np.int16)])
        hit: WakeHit | None = None
        while self._buffer.size >= self._chunk_samples:
            chunk = self._buffer[: self._chunk_samples]
            self._buffer = self._buffer[self._chunk_samples :]
            score = self._score(chunk)
            self._peak = max(self._peak, score)
            if score >= self._candidate_threshold:
                hit = WakeHit(score=score, confident=score >= self.threshold)
                self._buffer = np.zeros(0, dtype=np.int16)
                break

        if hit is not None:
            self._last_fire = now
            self.reset()
        return hit

    @property
    def threshold(self) -> float:
        """Darhol uyg'onish uchun kerakli ball."""
        return 1.0

    @abstractmethod
    def _score(self, chunk: np.ndarray) -> float:
        """Aynan `chunk_samples` uzunlikdagi kadrning ballini qaytaradi (0..1)."""

    def reset(self) -> None:
        """Ichki holatni tozalaydi (masalan, Jarvis gapirib bo'lgandan keyin)."""

    def close(self) -> None:
        """Resurslarni bo'shatadi."""


class OpenWakeWordDetector(WakeWordDetector):
    """openWakeWord — `hey_jarvis` modeli tayyor holda mavjud."""

    CHUNK_SAMPLES = 1280  # 80 ms @ 16 kHz — model shu o'lchamni kutadi

    def __init__(self, model_name: str = "hey_jarvis", threshold: float = 0.5,
                 cooldown_sec: float = 2.0, candidate_threshold: float | None = None) -> None:
        super().__init__(
            self.CHUNK_SAMPLES, cooldown_sec,
            candidate_threshold=threshold if candidate_threshold is None else candidate_threshold,
        )
        self._threshold = threshold

        from openwakeword.model import Model
        from openwakeword.utils import download_models

        # Modellar birinchi ishga tushirishda yuklab olinadi (keyin keshdan).
        try:
            download_models(model_names=[model_name])
        except Exception:
            log.warning("Model yuklab olinmadi, keshdagi nusxa ishlatiladi", exc_info=True)

        self._model = Model(wakeword_models=[model_name], inference_framework="onnx")
        self._key = model_name
        log.info("openWakeWord tayyor: %s (chegara %.2f, shubhali %.2f)",
                 model_name, threshold, self._candidate_threshold)

    @property
    def threshold(self) -> float:
        return self._threshold

    def _score(self, chunk: np.ndarray) -> float:
        scores = self._model.predict(chunk)
        # Model kalitni to'liq nom bilan qaytarishi mumkin — moslashuvchan qidiramiz.
        score = scores.get(self._key)
        if score is None:
            score = max(scores.values(), default=0.0)
        return float(score)

    def reset(self) -> None:
        reset_fn = getattr(self._model, "reset", None)
        if callable(reset_fn):
            reset_fn()


class PorcupineDetector(WakeWordDetector):
    """Picovoice Porcupine — `jarvis` built-in kalit so'zi bor."""

    def __init__(self, keyword: str = "jarvis", sensitivity: float = 0.5,
                 cooldown_sec: float = 2.0) -> None:
        import pvporcupine

        access_key = os.environ.get("PICOVOICE_ACCESS_KEY")
        if not access_key:
            raise RuntimeError(
                "Porcupine uchun `PICOVOICE_ACCESS_KEY` kerak "
                "(console.picovoice.ai dan bepul olinadi)."
            )

        self._porcupine = pvporcupine.create(
            access_key=access_key, keywords=[keyword], sensitivities=[sensitivity]
        )
        # Porcupine ball qaytarmaydi, faqat "topildi/yo'q" — shuning uchun
        # shubhali daraja ham yo'q, hamma chaqiruv ishonchli hisoblanadi.
        super().__init__(self._porcupine.frame_length, cooldown_sec, candidate_threshold=1.0)
        log.info("Porcupine tayyor: %s", keyword)

    def _score(self, chunk: np.ndarray) -> float:
        if self._porcupine.process(chunk.tolist()) >= 0:
            log.info("Uyg'otuvchi so'z eshitildi (porcupine)")
            return 1.0
        return 0.0

    def close(self) -> None:
        self._porcupine.delete()


def build_wake_detector(cfg: dict) -> WakeWordDetector | None:
    """Konfiguratsiyaga qarab mos aniqlagichni yaratadi. O'chirilgan bo'lsa `None`."""
    if not cfg.get("enabled", True):
        return None

    backend = str(cfg.get("backend", "openwakeword")).lower()
    threshold = float(cfg.get("threshold", 0.5))
    cooldown = float(cfg.get("cooldown_sec", 2.0))

    if backend == "porcupine":
        return PorcupineDetector(
            keyword=str(cfg.get("model", "jarvis")),
            sensitivity=threshold,
            cooldown_sec=cooldown,
        )
    if backend == "openwakeword":
        # Shubhali chegara asosiysidan past bo'lishi kerak, aks holda
        # ikkinchi bosqichning ma'nosi yo'q.
        candidate = float(cfg.get("candidate_threshold", threshold))
        return OpenWakeWordDetector(
            model_name=str(cfg.get("model", "hey_jarvis")),
            threshold=threshold,
            cooldown_sec=cooldown,
            candidate_threshold=min(candidate, threshold),
        )
    raise ValueError(f"Noma'lum uyg'otuvchi so'z backend'i: {backend}")
