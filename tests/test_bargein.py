"""Gapni bo'lish testlari.

Eng muhim ikki holat qarama-qarshi:
  * dinamikdan qaytgan Jarvisning o'z ovozi bo'linishga olib kelmasligi kerak;
  * foydalanuvchi gapirsa, darhol to'xtashi kerak.

Ikkisini bir sozlama bilan qoplash uchun chegara moslashadi, shuning uchun
testlar ham "shovqin darajasi" ni turlicha qilib beradi.
"""

from __future__ import annotations

import numpy as np

from jarvis.audio.bargein import BargeInWatcher, build_barge_in
from jarvis.audio.vad import SpeechDetector

FRAME = 320  # 20 ms @ 16 kHz


class AlwaysSpeech(SpeechDetector):
    """VAD nuqtai nazaridan hamma narsa nutq — aks sado ham shunday eshitiladi."""

    def is_speech(self, frame: np.ndarray) -> bool:
        return True


class NeverSpeech(SpeechDetector):
    def is_speech(self, frame: np.ndarray) -> bool:
        return False


def tone(level: float) -> np.ndarray:
    """Berilgan `frame_level` darajasiga teng keladigan kadr.

    `frame_level` RMS ni 8000 ga bo'ladi, shuning uchun doimiy qiymatli
    kadrning darajasi to'g'ridan-to'g'ri chiqadi.
    """
    return np.full(FRAME, int(level * 8000), dtype=np.int16)


def feed(watcher: BargeInWatcher, level: float, frames: int) -> bool:
    """Shuncha kadr beradi va bo'lish sodir bo'ldimi, shuni qaytaradi."""
    return any(watcher.push(tone(level)) for _ in range(frames))


def _watcher(detector: SpeechDetector | None = None, **kw) -> BargeInWatcher:
    return BargeInWatcher(detector or AlwaysSpeech(), frame_ms=20, **kw)


def test_own_voice_does_not_interrupt():
    """Dinamikdan qaytgan doimiy aks sado — bu bo'lish emas."""
    watcher = _watcher()

    assert feed(watcher, 0.30, 200) is False


def test_user_speech_over_the_echo_interrupts():
    """Aks sado ustidan gapirilsa, to'xtashi kerak."""
    watcher = _watcher()
    feed(watcher, 0.30, 50)  # fon o'lchanib oldi

    assert feed(watcher, 0.90, 30) is True


def test_quiet_room_is_sensitive():
    """Quloqchinda fon deyarli yo'q — oddiy gapirish ham yetadi."""
    watcher = _watcher()
    feed(watcher, 0.01, 50)

    assert feed(watcher, 0.25, 30) is True


def test_silence_never_interrupts_even_if_vad_says_speech():
    """Juda past daraja — VAD nima deganidan qat'i nazar, bu jimlik."""
    watcher = _watcher()

    assert feed(watcher, 0.005, 300) is False


def test_vad_must_agree():
    """Baland, lekin nutq emas (eshik taqillashi, musiqa zarbasi) — bo'lmaydi."""
    watcher = _watcher(NeverSpeech())

    assert feed(watcher, 0.95, 300) is False


def test_short_burst_is_ignored():
    """Bir zumlik shovqin gapni bo'lmasligi kerak."""
    watcher = _watcher(min_speech_ms=350)
    feed(watcher, 0.05, 50)

    # 350 ms = 17 kadr; 5 kadr (100 ms) yetmaydi
    assert feed(watcher, 0.90, 5) is False


def test_warmup_ignores_the_start_of_playback():
    """Ijro boshida fon hali o'lchanmagan — o'z ovozimizdan bo'linmasligi kerak."""
    watcher = _watcher(warmup_ms=300, min_speech_ms=100)

    # Gap boshidanoq baland: bu Jarvisning o'zi ijroga kirishgani
    assert feed(watcher, 0.60, 15) is False


def test_reset_forgets_the_previous_utterance():
    """Har bir yangi gap fonni qaytadan o'lchashi kerak."""
    watcher = _watcher()
    feed(watcher, 0.80, 60)  # baland fonga moslashdi
    watcher.reset()
    feed(watcher, 0.02, 50)  # yangi gap — endi jim

    assert feed(watcher, 0.30, 30) is True


def test_gate_follows_the_background():
    """Chegara fon bilan birga ko'tarilishi kerak — shu o'zi moslashishning o'zi."""
    quiet = _watcher()
    feed(quiet, 0.02, 60)
    loud = _watcher()
    feed(loud, 0.50, 60)

    assert loud.gate > quiet.gate


def test_build_respects_the_off_switch():
    assert build_barge_in({"barge_in": False}, AlwaysSpeech(), 20) is None
    assert build_barge_in({}, AlwaysSpeech(), 20) is not None
