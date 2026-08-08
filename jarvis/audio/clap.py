"""Ikki marta qarsak ("tars-tars") aniqlagichi.

Qarsak nutqdan ikki jihati bilan farq qiladi:
  1. Energiya keskin sakraydi va tez so'nadi (o'tkir zarba).
  2. Spektri keng — yuqori chastotalarda ham ko'p energiya bor,
     nutqda esa energiya asosan 300–2000 Hz oralig'ida to'planadi.

Ikkalasini birga tekshirish yolg'on ishga tushishlarni sezilarli kamaytiradi:
eshik qarsillashi birinchi shartni, gapirish ikkinchisini o'tolmaydi.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger("jarvis.audio.clap")

# Yuqori chastota chegarasi: shundan tepadagi energiya ulushiga qaraymiz.
HIGH_FREQ_HZ = 2000.0
# Qarsak uchun yuqori chastota energiyasining eng kam ulushi.
MIN_HIGH_FREQ_RATIO = 0.35
# Mutlaq eng kam RMS — mutlaq jimlikda shovqin kuchayishining oldini oladi.
MIN_ABSOLUTE_RMS = 700.0


@dataclass
class ClapDetector:
    """Kadrlarni birma-bir qabul qiladi, ikkinchi qarsak kelganda `True` qaytaradi.

    Vaqt **audio namunalari bo'yicha** o'lchanadi, real soat bo'yicha emas.
    Bu muhim: kadrlar navbatda to'planib qolsa (yadro band bo'lganda shunday
    bo'ladi), ular birdaniga ketma-ket qayta ishlanadi. Real soat bilan
    o'lchaganda 300 ms oraliqdagi ikki qarsak 2 ms deb hisoblanib, aniqlanmay
    qolardi. Audio soati esa qayta ishlash tezligiga bog'liq emas.
    """

    sample_rate: int = 16000
    onset_ratio: float = 8.0
    min_gap_sec: float = 0.12
    max_gap_sec: float = 0.70
    cooldown_sec: float = 2.0

    _noise_floor: float = 300.0
    _in_onset: bool = False
    _onsets: list[float] = field(default_factory=list)
    _clock: float = 0.0        # eshitilgan audio davomiyligi, soniyada
    _last_fire: float = -1e9   # oxirgi ishga tushish vaqti (audio soati bo'yicha)

    def reset(self) -> None:
        self._in_onset = False
        self._onsets.clear()

    def push(self, frame: np.ndarray) -> bool:
        """Bitta kadrni qayta ishlaydi. Ikki qarsak topilsa `True`."""
        # Soat kadr boshida o'qiladi — shu kadr aynan qaysi vaqtga tegishli ekani.
        now = self._clock
        self._clock += frame.size / self.sample_rate

        if now - self._last_fire < self.cooldown_sec:
            return False

        samples = frame.astype(np.float32)
        rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0

        threshold = max(self._noise_floor * self.onset_ratio, MIN_ABSOLUTE_RMS)
        loud = rms > threshold

        if not loud:
            # Faqat jim kadrlarda shovqin darajasini yangilaymiz (sekin EMA).
            self._noise_floor = 0.95 * self._noise_floor + 0.05 * max(rms, 1.0)
            self._in_onset = False
            self._prune(now)
            return False

        if self._in_onset:
            # Bitta zarbaning davomi — yangi onset emas.
            return False
        self._in_onset = True

        if not self._is_broadband(samples):
            return False

        self._prune(now)
        self._onsets.append(now)

        if len(self._onsets) >= 2:
            gap = self._onsets[-1] - self._onsets[-2]
            if self.min_gap_sec <= gap <= self.max_gap_sec:
                log.info("Ikki qarsak aniqlandi (oraliq %.0f ms)", gap * 1000)
                self._last_fire = now
                self.reset()
                return True

        return False

    def _prune(self, now: float) -> None:
        """Juftlik hosil qilolmaydigan eski zarbalarni unutamiz."""
        self._onsets = [t for t in self._onsets if now - t <= self.max_gap_sec]

    def _is_broadband(self, samples: np.ndarray) -> bool:
        """Yuqori chastota energiyasi ulushi qarsakka xosmi?"""
        if samples.size < 64:
            return False
        windowed = samples * np.hanning(samples.size)
        spectrum = np.abs(np.fft.rfft(windowed))
        power = np.square(spectrum)
        total = float(power.sum())
        if total <= 0.0:
            return False

        freqs = np.fft.rfftfreq(samples.size, d=1.0 / self.sample_rate)
        high = float(power[freqs >= HIGH_FREQ_HZ].sum())
        ratio = high / total
        return ratio >= MIN_HIGH_FREQ_RATIO
