"""Ovozli tasdiqni tanish: «ha, ruxsat beraman» — bu rozilikmi?

Qoida ataylab xavfsizlik tomonga og'gan: rad so'zi topilsa, rozilik so'zi
ham bo'lsa baribir RAD deb o'qiladi («ruxsat bermayman» ichida «ruxsat»
bor!). Ikkalasi ham topilmasa — noaniq, va noaniqlikda hech qachon
"ruxsat" deb taxmin qilmaymiz: qayta so'raymiz.

STT xatolariga chidamlilik uchun so'zlar tutuq belgisisiz solishtiriladi:
«yo'q», «yoq», «yuq» — bittasi.
"""

from __future__ import annotations

import re

# Tutuq belgilarining barcha ko'rinishlari — STT qaysi birini yozishi noma'lum.
_APOSTROPHES = "'‘’ʻʼ`´"
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

YES_WORDS = frozenset({
    "ha", "xa", "xop", "hop", "mayli", "davom", "bajar", "bajaraver",
    "boshla", "boshlayver", "qil", "qilaver", "ruxsat", "beraman", "rozi",
    "roziman", "ok", "okey", "okay", "yes", "tasdiq", "tasdiqlayman",
    "albatta", "boladi", "bolsin", "yaxshi",
})

NO_WORDS = frozenset({
    "yoq", "yuq", "toxta", "tuxta", "bekor", "qilma", "qilmang", "bajarma",
    "berma", "bermayman", "bermang", "rad", "stop", "no",
})

# Ikki so'zli rad iboralari — so'zma-so'z tekshiruvda ko'rinmaydi.
NO_PHRASES = ("kerak emas", "mumkin emas", "hojat yoq", "shart emas")


def _tokens(text: str) -> list[str]:
    cleaned = text.lower()
    for mark in _APOSTROPHES:
        cleaned = cleaned.replace(mark, "")
    return [m.group() for m in _WORD.finditer(cleaned)]


def parse_consent(text: str) -> bool | None:
    """Matndan rozilikni o'qiydi: True / False / None (noaniq)."""
    words = _tokens(text or "")
    if not words:
        return None

    joined = " ".join(words)
    if any(phrase in joined for phrase in NO_PHRASES):
        return False
    if any(word in NO_WORDS for word in words):
        return False
    if any(word in YES_WORDS for word in words):
        return True
    return None


def consent_prompt(action: str, detail: str) -> str:
    """Tasdiq savolining ovozda aytiladigan ko'rinishi.

    Uzun buyruqni ovozda o'qish befoyda — ekranda ko'rinib turibdi.
    """
    piece = (detail or "").strip().splitlines()[0] if detail else ""
    if len(piece) > 70:
        piece = ""
    parts = ["Ruxsat kerak.", action.strip()]
    if piece:
        parts.append(piece)
    parts.append("Ha yoki yo'q?")
    return " ".join(p for p in parts if p)
