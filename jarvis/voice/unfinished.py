"""Gap tugadimi yoki odam hali o'ylayaptimi?

Jimlik taymeri bitta savolga javob bera olmaydi: «bir soniya jimlik — gap
tugadi» degani ham, «hali davom etadi» degani ham bo'lishi mumkin. Qisqa
kutsa, odamning o'ylanib qolgani gapni bo'lib yuboradi; uzoq kutsa, har
bir javob ortiqcha soniyalar bilan kechikadi.

Shuning uchun qaror ovoz emas, MATN bo'yicha qabul qilinadi. Gap
«...keyin», «...va», «...ya'ni» yoki «aaa» bilan tugagan bo'lsa — odam
hali gapirmoqchi. Nuqta qo'yilgan gap esa darhol javob oladi.

Bu ro'yxat qasddan qisqa: faqat o'zbek tilida gap OXIRIDA kelganda deyarli
har doim davomi borligini bildiradigan so'zlar. Shubhali so'zni qo'shish
xavfli — u har bir gapdan keyin bekorga kutishga olib keladi.
"""

from __future__ import annotations

import re

_APOSTROPHES = "'‘’ʻʼ`´"
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

# Bog'lovchilar va ko'makchilar: bulardan keyin albatta davomi keladi.
CONTINUATION_WORDS = frozenset({
    "va", "hamda", "yoki", "lekin", "ammo", "biroq",
    "keyin", "so'ng", "song", "avval", "oldin",
    "yani", "yoqi", "masalan", "chunki", "agar", "shuning",
    "uchun", "bilan", "haqida", "orqali", "tomon",
    "qilib", "qilsa", "bo'lsa", "bolsa", "desa", "deb",
    "menga", "manga", "senga", "unga", "shunga", "bunga",
    "bu", "shu", "u", "ana", "mana",
})

# Ikkilanish tovushlari: «aaa», «eee», «mmm», «e'e», «hmm».
_HESITATION = re.compile(r"^(a+|e+|o+|i+|m+|h+m*|u+h*)$")


def _tokens(text: str) -> list[str]:
    cleaned = (text or "").lower()
    for mark in _APOSTROPHES:
        cleaned = cleaned.replace(mark, "")
    return [m.group() for m in _WORD.finditer(cleaned)]


def looks_unfinished(text: str) -> bool:
    """Gap tugamagandek ko'rinsa True.

    Uch belgi:
      * matn ochiq bog'lovchi bilan tugagan («...va», «...keyin»);
      * oxirgi so'z ikkilanish tovushi («aaa», «mmm»);
      * matn juda qisqa va tinish belgisi yo'q («men» — bu gap emas).
    """
    raw = (text or "").strip()
    if not raw:
        return False

    # Aniq yakun belgisi bo'lsa, kutish shart emas.
    if raw[-1] in ".!?…":
        return False

    words = _tokens(raw)
    if not words:
        return False

    last = words[-1]
    if _HESITATION.match(last):
        return True
    if last in CONTINUATION_WORDS:
        return True

    # Bitta so'z — bu buyruq ham bo'lishi mumkin («to'xta», «ha»), shuning
    # uchun faqat ikkilanish va bog'lovchilar hisobga olinadi. Qolganini
    # taxmin qilmaymiz: noto'g'ri kutish javobni sekinlashtiradi.
    return False
