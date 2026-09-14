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

# «To'xta» bilan birga kelishi mumkin bo'lgan, o'zi ma'no tashimaydigan
# so'zlar. Ular buyruq emas, shuning uchun «to'xta» ni yolg'iz deb
# hisoblashga xalaqit bermaydi.
_FILLERS = frozenset({"ha", "yoq", "iltimos", "endi", "hoy", "hey", "jarvis", "bir", "hozir"})


def is_stop_speaking(text: str) -> bool:
    """«To'xta» — gapirishni to'xtat, lekin suhbatni yopma.

    Faqat YOLG'IZ «to'xta» shunday o'qiladi. «To'xta, Instagramga kir»
    degan gap — bu buyruq: odam avval gapni bo'ladi, keyin nima qilish
    kerakligini aytadi. Ilgari bunday gap butunlay tashlab yuborilardi va
    foydalanuvchi buyrug'ining boshi yo'qolib ketardi.
    """
    words = _tokens(text)
    if not words or len(words) > 3:
        return False

    joined = " ".join(words)
    hit = (any(phrase in joined for phrase in STOP_PHRASES)
           or any(word in STOP_WORDS for word in words))
    if not hit:
        return False

    # Buyruq qo'shilgan bo'lsa, bu «to'xta» emas — buni miyaga berish kerak.
    extra = [w for w in words
             if w not in STOP_WORDS and w not in _FILLERS
             and not any(w in phrase for phrase in STOP_PHRASES)]
    return not extra


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
