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


def _block_end(lines: list[str], start: int, indent: int) -> int:
    """Blok qayerda tugaydi: chekinishi sarlavhanikidan katta bo'lmagan
    birinchi ma'noli qator. Bo'sh qatorlar va izohlar blokni tugatmaydi."""
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _indent_of(lines[index]) <= indent:
            return index
    return len(lines)


def _find_block(lines: list[str], name: str, start: int, end: int,
                indent: int | None) -> int | None:
    """`name:` sarlavhasini berilgan oraliqdan qidiradi (qiymatsiz kalit)."""
    for index in range(start, end):
        match = _LINE.match(lines[index])
        if not match or match.group("key") != name or match.group("value"):
            continue
        if indent is not None and _indent_of(lines[index]) != indent:
            continue
        return index
    return None


def set_in_block(text: str, block: str, values: dict[str, object],
                 create: bool = False) -> str:
    """`block:` ichidagi kalitlarni yangilaydi; bo'lmagani qo'shiladi.

    `block` nuqta bilan yozilishi mumkin: «activation.wake_word» — u holda
    ichma-ich qidiriladi. `create=True` bo'lsa, yo'q bloklar yaratiladi:
    sozlama faylida hali o'sha bo'lim bo'lmagan bo'lishi mumkin.

    Blok o'z sarlavhasidan chuqurroq chekinishga ega qatorlar bilan
    aniqlanadi — YAML'ning o'zi ham shunday ishlaydi.
    """
    lines = text.splitlines()
    path = [part for part in block.split(".") if part]
    if not path:
        raise KeyError("bo'sh blok nomi")

    scope_start, scope_end = 0, len(lines)
    parent_indent = -2          # xayoliy ildiz: bolalari 0 chekinishda

    for depth, name in enumerate(path):
        expected = parent_indent + 2
        # Bitta bo'lakli nom (eski chaqiruvlar) — chekinishga qaramaymiz
        want_indent = None if len(path) == 1 else expected
        index = _find_block(lines, name, scope_start, scope_end, want_indent)
        if index is None:
            if not create:
                raise KeyError(f"`{name}:` bloki topilmadi")
            # Blokni ota-blokning oxiriga qo'shamiz
            insert_at = scope_end
            if insert_at > 0 and lines[insert_at - 1].strip() and expected == 0:
                lines.insert(insert_at, "")     # yuqori darajada bo'sh qator bilan ajratamiz
                insert_at += 1
            lines.insert(insert_at, f"{' ' * expected}{name}:")
            index = insert_at
            scope_start, scope_end = index + 1, index + 1
            parent_indent = expected
            continue
        block_indent = _indent_of(lines[index])
        scope_start = index + 1
        scope_end = _block_end(lines, index, block_indent)
        parent_indent = block_indent

    remaining = dict(values)
    for index in range(scope_start, scope_end):
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
        inner = " " * (parent_indent + 2)
        added = [f"{inner}{key}: {_format(value)}" for key, value in remaining.items()]
        lines[scope_end:scope_end] = added

    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _format(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(f'"{item}"' for item in value) + "]"
    return f'"{value}"'


def patch_file(path: Path, block: str, values: dict[str, object],
               create: bool = False) -> Path:
    """Faylni yangilaydi. Eski nusxa `.bak` sifatida saqlanadi.

    Yozishdan oldin natija YAML sifatida o'qib ko'riladi — buzilgan fayl
    diskka tushmasligi kerak.
    """
    import yaml

    original = path.read_text()
    updated = set_in_block(original, block, values, create=create)

    yaml.safe_load(updated)  # buzilgan bo'lsa shu yerda xato beradi

    path.with_suffix(path.suffix + ".bak").write_text(original)
    path.write_text(updated)
    return path
