"""Suhbatni boshqaradigan qisqa buyruqlar.

Bular miyaga umuman bormaydi: «bo'ldi, yakunla» degan gapni Claude'ga
yuborib, javob kutib o'tirish ham sekin, ham keraksiz. Ular shu yerda,
matn darajasida tanib olinadi.

Tanish qoidasi ehtiyotkor: faqat aniq buyruq yakunlaydi. «Bo'ldimi?» yoki
«bu ish tugadi» degan gaplar suhbat o'rtasida ham aytiladi, ularni yakun
deb tushunsak, Jarvis gap o'rtasida jim bo'lib qolardi.
"""

from __future__ import annotations

import re

_APOSTROPHES = "'‘’ʻʼ`´"
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

# Bitta so'zning o'zi yakun uchun yetarli.
END_WORDS = frozenset({
    "yakunla", "yakunlaymiz", "tugat", "tugatdik", "xayr", "salomat",
    "yop", "yopamiz", "chiqamiz", "bormadim", "ketdim",
})

# Ikki so'zli aniq buyruqlar — alohida so'z sifatida noaniq bo'lganlari.
END_PHRASES = (
    "suhbatni yakunla", "suhbatni tugat", "suhbat tugadi",
    "boldi yetadi", "boldi bas", "hozircha yetadi", "keyin gaplashamiz",
    "kerak emas rahmat", "rahmat yetadi", "boshqa kerak emas",
    "ozingni yop", "ekrandan chiq", "yopib qoy",
)


def _tokens(text: str) -> list[str]:
    cleaned = (text or "").lower()
    for mark in _APOSTROPHES:
        cleaned = cleaned.replace(mark, "")
    return [m.group() for m in _WORD.finditer(cleaned)]


def is_end_of_conversation(text: str) -> bool:
    """Foydalanuvchi suhbatni yakunlashni so'radimi?"""
    words = _tokens(text)
    if not words:
        return False

    joined = " ".join(words)
    if any(phrase in joined for phrase in END_PHRASES):
        return True

    # Yolg'iz so'z faqat gap qisqa bo'lganda yakun hisoblanadi: uzun gap
    # ichidagi «tugat» boshqa narsaga tegishli bo'lishi mumkin.
    if len(words) <= 3 and any(word in END_WORDS for word in words):
        return True
    return False
