"""Gapirish tugaganini aniqlash (endpointing).

Uyg'otuvchi so'zdan keyin Jarvis yozib olishni boshlaydi va foydalanuvchi
gapirishni to'xtatganda avtomatik to'xtaydi. Buning uchun har bir kadr
"nutq" yoki "jimlik" deb belgilanadi va ketma-ket jimlik hisoblanadi.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

log = logging.getLogger("jarvis.audio.vad")


class SpeechDetector(ABC):
    @abstractmethod
    def is_speech(self, frame: np.ndarray) -> bool:
        """Kadrda nutq bormi?"""


class WebRtcSpeechDetector(SpeechDetector):
    """WebRTC VAD — yengil va tez, real vaqtda ishlashga mo'ljallangan."""

    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 2) -> None:
        import webrtcvad

        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError(f"WebRTC VAD {sample_rate} Hz ni qo'llamaydi")
        self._vad = webrtcvad.Vad(max(0, min(3, aggressiveness)))
        self._sample_rate = sample_rate

    def is_speech(self, frame: np.ndarray) -> bool:
        # WebRTC faqat 10/20/30 ms kadrlarni qabul qiladi.
        allowed = {self._sample_rate * ms // 1000 for ms in (10, 20, 30)}
        if frame.size not in allowed:
            return False
        return self._vad.is_speech(frame.astype(np.int16).tobytes(), self._sample_rate)


class EnergySpeechDetector(SpeechDetector):
    """Zaxira variant: oddiy energiya chegarasi (webrtcvad o'rnatilmagan bo'lsa)."""

    def __init__(self, threshold: float = 500.0, adapt: float = 0.02) -> None:
        self._floor = threshold
        self._adapt = adapt

    def is_speech(self, frame: np.ndarray) -> bool:
        if frame.size == 0:
            return False
        rms = float(np.sqrt(np.mean(np.square(frame.astype(np.float32)))))
        speaking = rms > self._floor * 2.5
        if not speaking:
            self._floor = (1 - self._adapt) * self._floor + self._adapt * max(rms, 1.0)
        return speaking


@dataclass
class Endpointer:
    """Nutqni yig'adi va foydalanuvchi jim bo'lganda `finished` bo'ladi.

    Ishlatilishi::

        ep = Endpointer(detector, frame_ms=20, silence_ms=900, max_sec=30)
        for frame in frames:
            ep.push(frame)
            if ep.finished:
                audio = ep.result()
                break
    """

    detector: SpeechDetector
    frame_ms: int = 20
    silence_ms: int = 900
    max_utterance_sec: float = 30.0
    # Yozib olishni boshlash uchun kerakli ketma-ket nutq kadrlari (chertishlarni filtrlaydi)
    speech_onset_frames: int = 2

    _frames: list[np.ndarray] = None  # type: ignore[assignment]
    _silence_run: int = 0
    _speech_run: int = 0
    _started: bool = False
    _finished: bool = False

    def __post_init__(self) -> None:
        self._frames = []

    @property
    def started(self) -> bool:
        """Foydalanuvchi gapira boshladimi?"""
        return self._started

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def duration_sec(self) -> float:
        return len(self._frames) * self.frame_ms / 1000.0

    def prime(self, audio: np.ndarray) -> None:
        """Oldindan yozilgan audioni (preroll) qo'shadi."""
        if audio.size:
            self._frames.append(audio.astype(np.int16))

    def push(self, frame: np.ndarray) -> None:
        if self._finished:
            return

        self._frames.append(frame.astype(np.int16))
        speaking = self.detector.is_speech(frame)

        if speaking:
            self._silence_run = 0
            self._speech_run += 1
            if not self._started and self._speech_run >= self.speech_onset_frames:
                self._started = True
        else:
            self._speech_run = 0
            if self._started:
                self._silence_run += 1

        silence_limit = max(1, self.silence_ms // max(1, self.frame_ms))
        if self._started and self._silence_run >= silence_limit:
            self._finished = True
            log.debug("Gapirish tugadi (%.1f s)", self.duration_sec)
        elif self.duration_sec >= self.max_utterance_sec:
            self._finished = True
            log.info("Maksimal davomiylikka yetildi (%.0f s)", self.max_utterance_sec)

    def result(self) -> np.ndarray:
        """Yig'ilgan audioni bitta massiv qilib qaytaradi."""
        if not self._frames:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate(self._frames)

    def reset(self) -> None:
        self._frames = []
        self._silence_run = 0
        self._speech_run = 0
        self._started = False
        self._finished = False


def build_speech_detector(cfg: dict, sample_rate: int) -> SpeechDetector:
    """Konfiguratsiyaga qarab detektor yaratadi, kerak bo'lsa zaxiraga o'tadi."""
    backend = str(cfg.get("backend", "webrtcvad")).lower()
    if backend == "webrtcvad":
        try:
            return WebRtcSpeechDetector(sample_rate, int(cfg.get("aggressiveness", 2)))
        except Exception:
            log.warning("webrtcvad ishlamadi, energiya detektoriga o'tildi", exc_info=True)
    return EnergySpeechDetector()
