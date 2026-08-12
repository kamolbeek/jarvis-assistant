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
    "cancel", "kensel", "otmena",
    "yakunla", "yakunlaymiz", "tugat", "tugatdik", "xayr", "salomat",
    "yop", "yopamiz", "chiqamiz", "bormadim", "ketdim",
})

# Ikki so'zli aniq buyruqlar — alohida so'z sifatida noaniq bo'lganlari.
END_PHRASES = (
    "cancel", "bekor qil", "hammasini yop", "otchir",
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


# «To'xta» — bu yakun emas. Jarvis gapirishdan to'xtaydi, lekin suhbat
# davom etadi va sahna ochiq qoladi. Ikkisini ajratish muhim: «to'xta»
# deganda hammasi yopilib ketsa, foydalanuvchi qaytadan chaqirishga majbur
# bo'lardi.
STOP_WORDS = frozenset({"toxta", "tuxta", "jim", "bas", "shosh"})
STOP_PHRASES = ("jim bol", "bas qil", "gapirma", "toxtat")


def is_stop_speaking(text: str) -> bool:
    """«To'xta» — gapirishni to'xtat, lekin suhbatni yopma."""
    words = _tokens(text)
    if not words or len(words) > 3:
        return False

    joined = " ".join(words)
    return (any(phrase in joined for phrase in STOP_PHRASES)
            or any(word in STOP_WORDS for word in words))


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
