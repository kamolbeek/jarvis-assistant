"""Audio qurilmasini nomi bo'yicha topish.

Sozlamada qurilmani raqami bilan ko'rsatish mumkin, lekin raqam barqaror
emas: iPhone yaqin kelsa yoki quloqchin ulansa, indekslar siljiydi. Nom esa
o'zgarmaydi — shuning uchun sozlamada nom turadi.

Muammo shundaki, `sounddevice` nomni AYNAN (registrni hisobga olib) qidiradi:
bir dona ortiqcha probel yoki boshqacha qavs — va «No input device matching…»
degan xato chiqadi. Bu yerda moslashtirish yumshoqroq: registr, ortiqcha
probel va shunga o'xshash mayda farqlar kechiriladi.
"""

from __future__ import annotations

import difflib
import logging
import re

log = logging.getLogger("jarvis.audio.devices")


def _normalise(text: str) -> str:
    """Taqqoslash uchun sodda ko'rinish: kichik harf, yagona probel."""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def _devices(kind: str) -> list[tuple[int, str]]:
    import sounddevice as sd

    key = f"max_{kind}_channels"
    return [(index, str(info["name"]))
            for index, info in enumerate(sd.query_devices())
            if info[key] > 0]


def input_devices() -> list[tuple[int, str]]:
    """(indeks, nom) — faqat kirish qurilmalari."""
    return _devices("input")


def output_devices() -> list[tuple[int, str]]:
    """(indeks, nom) — faqat chiqish qurilmalari."""
    return _devices("output")


def resolve_output_device(value: object) -> int | None:
    """Dinamik uchun — kirishnikiga o'xshash, faqat chiqish ro'yxatidan."""
    return _resolve(value, output_devices(), "chiqish")


def resolve_input_device(value: object) -> int | None:
    """Sozlamadagi qiymatni qurilma indeksiga aylantiradi.

    None yoki bo'sh satr -> None (tizim standarti).
    Raqam -> o'sha indeks.
    Nom   -> yumshoq moslashtirish; topilmasa ValueError (ro'yxat bilan).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)

    return _resolve(text, input_devices(), "kirish")


def _resolve(value: object, devices: list[tuple[int, str]], kind: str) -> int | None:
    """Umumiy moslashtirish: aynan -> ichida -> teskari -> eng o'xshashi."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if not devices:
        raise ValueError(f"{kind.capitalize()} qurilmasi topilmadi")

    target = _normalise(text)
    names = {index: _normalise(name) for index, name in devices}

    for index, name in names.items():                 # aynan mos
        if name == target:
            return index
    for index, name in names.items():                 # ichida bor
        if target in name:
            return index
    for index, name in names.items():                 # teskarisi
        if name in target:
            return index

    # Oxirgi urinish: eng o'xshashi (masalan bitta harf farq qilsa)
    close = difflib.get_close_matches(target, list(names.values()), n=1, cutoff=0.75)
    if close:
        for index, name in names.items():
            if name == close[0]:
                log.warning("«%s» aynan topilmadi — eng yaqini: «%s»",
                            text, dict(devices)[index])
                return index

    listing = "\n  ".join(f"{index}. {name}" for index, name in devices)
    setting = "audio.input_device" if kind == "kirish" else "audio.output_device"
    raise ValueError(
        f"«{text}» nomli {kind} qurilmasi yo'q. Mavjudlari:\n  {listing}\n"
        f"Sozlamadagi {setting} ni shulardan biriga to'g'rilang "
        "(`python -m jarvis mic-test` yordam beradi)."
    )
