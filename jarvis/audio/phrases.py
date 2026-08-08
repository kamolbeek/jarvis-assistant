"""Chaqiruv iborasini matndan tanish.

Tayyor uyg'otuvchi so'z modeli faqat bittasini biladi — «hey jarvis». «Salom
Jarvis» va «Hi Jarvis» uchun ikkinchi bosqich kerak: past chegaradan o'tgan
shubhali ovoz matnga aylantiriladi va shu yerda tekshiriladi.

STT hech qachon aynan yozmaydi. Haqiqiy misol — foydalanuvchi «hey jarvis»
deganda ElevenLabs «Hai, Jervis» deb qaytardi. Shuning uchun taqqoslash
qat'iy emas: har bir so'z o'xshashlik darajasi bilan solishtiriladi.

Mantiq ikki qismdan iborat:
  * **langar** — matnda «jarvis»ga o'xshash so'z bo'lishi shart. Bu eng muhim
    shart, chunki ismsiz gap bizga qaratilmagan;
  * **salomlashuv** — sozlamadagi iboralardan olingan so'zlar (hey, hi, salom).

Langarsiz hech qachon uyg'onmaydi. Ro'yxatga yalang «jarvis» qo'shilsa,
salomlashuv talab qilinmaydi.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

log = logging.getLogger("jarvis.audio.phrases")

ANCHOR = "jarvis"
DEFAULT_PHRASES = ("hey jarvis", "hi jarvis", "salom jarvis")

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def normalize(text: str) -> list[str]:
    """Matnni kichik harfli so'zlarga ajratadi, tinish belgilarini tashlaydi.

    O'zbek lotin yozuvidagi `'` (tutuq) so'z ichida qoladigan belgi emas,
    shuning uchun `\\W` bilan tushib ketishi bizga mos: «ko'r» -> ko, r.
    Chaqiruv iboralarida bunday so'z yo'q.
    """
    return [match.group().lower() for match in _WORD.finditer(text or "")]


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


class PhraseMatcher:
    """Sozlamadagi chaqiruv iboralarini matnda qidiradi."""

    def __init__(
        self,
        phrases: tuple[str, ...] | list[str] = DEFAULT_PHRASES,
        anchor: str = ANCHOR,
        min_ratio: float = 0.7,
    ) -> None:
        self._anchor = anchor.lower()
        self._min_ratio = min_ratio

        greetings: set[str] = set()
        bare = False
        for phrase in phrases:
            words = [w for w in normalize(phrase) if w]
            others = [w for w in words if not self._is_anchor(w)]
            if not others:
                # Faqat ism: «jarvis» — salomlashuv talab qilinmaydi
                bare = bare or bool(words)
            greetings.update(others)

        self._greetings = frozenset(greetings)
        self._bare_anchor = bare

    @property
    def greetings(self) -> frozenset[str]:
        return self._greetings

    def _is_anchor(self, word: str) -> bool:
        return similarity(word, self._anchor) >= self._min_ratio

    def matches(self, text: str) -> bool:
        """Matn chaqiruvga o'xshaydimi?"""
        words = normalize(text)
        if not words:
            return False

        if not any(self._is_anchor(word) for word in words):
            return False

        if self._bare_anchor:
            log.debug("Chaqiruv tanildi (yalang ism): %s", text)
            return True

        for word in words:
            for greeting in self._greetings:
                if similarity(word, greeting) >= self._min_ratio:
                    log.debug("Chaqiruv tanildi (%s): %s", greeting, text)
                    return True
        return False


def build_matcher(cfg: dict) -> PhraseMatcher | None:
    """Sozlamaga qarab tanigichni yaratadi; iboralar bo'lmasa `None`."""
    phrases = cfg.get("phrases")
    if phrases is None:
        phrases = list(DEFAULT_PHRASES)
    phrases = [str(p) for p in phrases if str(p).strip()]
    if not phrases:
        return None
    return PhraseMatcher(
        phrases=phrases,
        min_ratio=float(cfg.get("phrase_ratio", 0.7)),
    )
