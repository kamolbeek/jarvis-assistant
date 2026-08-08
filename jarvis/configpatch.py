"""Sozlama faylidagi bitta qiymatni xavfsiz almashtirish.

Nima uchun kerak: YAML bo'sh joyga sezgir va uni qo'lda tahrirlash oson
buziladi — bitta ortiqcha probel butun faylni yaroqsiz qiladi va Jarvis
umuman ishga tushmaydi.

Nima uchun `yaml.safe_load` + `safe_dump` emas: u faylni qayta yozganda
barcha izohlarni yo'q qiladi. Sozlama faylimizdagi izohlar — hujjatning
o'zi, ularni yo'qotish yaramaydi. Shuning uchun faqat kerakli qatorni
almashtiramiz, qolgan hamma narsa tegilmaydi.
"""

from __future__ import annotations

import re
from pathlib import Path

# `    threshold: 0.5    # izoh` — qiymatni ajratib, izohni saqlaymiz.
_LINE = re.compile(
    r"^(?P<indent>\s*)(?P<key>[A-Za-z_][\w]*)\s*:\s*(?P<value>[^#\n]*?)\s*(?P<comment>#.*)?$"
)


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def set_in_block(text: str, block: str, values: dict[str, object]) -> str:
    """`block:` ichidagi kalitlarni yangilaydi; bo'lmagani qo'shiladi.

    Blok o'z sarlavhasidan chuqurroq chekinishga ega qatorlar bilan
    aniqlanadi — YAML'ning o'zi ham shunday ishlaydi.
    """
    lines = text.splitlines()
    start = None
    block_indent = 0

    for index, line in enumerate(lines):
        match = _LINE.match(line)
        if match and match.group("key") == block and not match.group("value"):
            start = index
            block_indent = _indent_of(line)
            break

    if start is None:
        raise KeyError(f"`{block}:` bloki topilmadi")

    # Blokning oxiri: chekinishi sarlavhanikidan katta bo'lmagan birinchi
    # ma'noli qator. Bo'sh qatorlar va izohlar blokni tugatmaydi.
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _indent_of(lines[index]) <= block_indent:
            end = index
            break

    remaining = dict(values)
    for index in range(start + 1, end):
        match = _LINE.match(lines[index])
        if not match:
            continue
        key = match.group("key")
        if key not in remaining:
            continue
        comment = match.group("comment")
        tail = f"  {comment}" if comment else ""
        lines[index] = f"{match.group('indent')}{key}: {_format(remaining.pop(key))}{tail}"

    if remaining:
        # Yo'q kalitlarni blok oxiriga qo'shamiz — ichkaridagi chekinish bilan.
        inner = " " * (block_indent + 2)
        added = [f"{inner}{key}: {_format(value)}" for key, value in remaining.items()]
        lines[end:end] = added

    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _format(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(f'"{item}"' for item in value) + "]"
    return f'"{value}"'


def patch_file(path: Path, block: str, values: dict[str, object]) -> Path:
    """Faylni yangilaydi. Eski nusxa `.bak` sifatida saqlanadi.

    Yozishdan oldin natija YAML sifatida o'qib ko'riladi — buzilgan fayl
    diskka tushmasligi kerak.
    """
    import yaml

    original = path.read_text()
    updated = set_in_block(original, block, values)

    yaml.safe_load(updated)  # buzilgan bo'lsa shu yerda xato beradi

    path.with_suffix(path.suffix + ".bak").write_text(original)
    path.write_text(updated)
    return path
