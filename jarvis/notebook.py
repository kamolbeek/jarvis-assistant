"""Daftarlar — Jarvisning o'zi yozib boradigan matn fayllari.

Nega sqlite xotirasidan tashqari yana shu kerak. `memory.db` — kalit/qiymat
juftliklari: mashina uchun qulay, odam uchun yopiq. Siz esa «nima eslab
qolgansan?» deb so'raganda ochib ko'rishni, xato yozilganini o'chirishni va
qo'lda bir narsa qo'shishni xohlaysiz. Shuning uchun bu yerdagilar oddiy
Markdown fayllar: `~/.jarvis/` ichida turadi, istalgan muharrirda ochiladi.

To'rtta daftar, to'rt xil ish uchun:

    men.md      Siz haqingizda: kim, nima bilan shug'ullanadi, nimani
                yoqtiradi, qanday gapiradi. Jarvis suhbatdan o'zi to'playdi.
    qoidalar.md «Bundan keyin bunday qil / bunday qilma» — sizning
                ko'rsatmalaringiz. Aytilgandan keyin doim amal qiladi.
    xatolar.md  Qilingan xatolar va ularni takrorlamaslik uchun xulosa.
    lugat.md    Siz tushunmagan so'zlar va ularning ma'nosi. «Karnaval nima
                degani?» deb so'raganingizda yoziladi va keyin o'sha so'zni
                ishlatishdan oldin izohlanadi.

Hammasi har bir suhbat boshida tizim ko'rsatmasiga qo'shiladi — ya'ni
Jarvis ularni «o'qishni unutmaydi».

Fayllar ataylab oddiy: sarlavha, so'ng sana bilan belgilangan qatorlar.
Formatni murakkablashtirsak, uni tahrirlash noqulay bo'lardi va daftarning
butun ma'nosi shunda edi — uni ODAM ham o'qiy olishi.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from .config import expand

log = logging.getLogger("jarvis.notebook")

NOTEBOOK_DIR = expand("~/.jarvis")

# Bitta daftardan tizim ko'rsatmasiga shuncha belgi olinadi. Cheksiz o'sib
# ketgan fayl butun kontekstni yeb qo'yishi mumkin — eng yangi yozuvlar
# muhimroq, shuning uchun oxiridan kesiladi.
MAX_PROMPT_CHARS = 4000

# Bitta yozuvning uzunligi.
MAX_ENTRY_CHARS = 1000


@dataclass(frozen=True)
class Note:
    """Bitta daftar."""

    key: str          # asboblar va kod uchun qisqa nom
    filename: str
    title: str        # fayl ichidagi sarlavha
    purpose: str      # ko'rsatmaga qo'shiladigan izoh

    @property
    def path(self) -> Path:
        return NOTEBOOK_DIR / self.filename


NOTES: tuple[Note, ...] = (
    Note(
        key="men",
        filename="men.md",
        title="Kamoliddin haqida",
        purpose="foydalanuvchi haqida bilganlaring: ishi, odatlari, "
                "afzalliklari, gapirish uslubi",
    ),
    Note(
        key="qoidalar",
        filename="qoidalar.md",
        title="Qoidalar",
        purpose="foydalanuvchi bergan doimiy ko'rsatmalar — «bundan keyin "
                "shunday qil», «bunday qilma»",
    ),
    Note(
        key="xatolar",
        filename="xatolar.md",
        title="Xatolar va xulosalar",
        purpose="qilingan xatolar va ularni takrorlamaslik uchun xulosa",
    ),
    Note(
        key="lugat",
        filename="lugat.md",
        title="Lug'at",
        purpose="foydalanuvchi tushunmagan so'zlar va ularning ma'nosi",
    ),
)

BY_KEY = {note.key: note for note in NOTES}

# Turli atama bilan aytilganda ham to'g'ri daftar topilsin.
ALIASES = {
    "profil": "men", "men haqimda": "men", "haqimda": "men", "uslub": "men",
    "qoida": "qoidalar", "korsatma": "qoidalar", "ko'rsatma": "qoidalar",
    "xato": "xatolar", "kamchilik": "xatolar",
    "soz": "lugat", "so'z": "lugat", "atama": "lugat", "lug'at": "lugat",
}


def resolve(name: str) -> Note | None:
    """Daftar nomini topadi. Noma'lum nom uchun `None`."""
    key = str(name).strip().casefold()
    key = ALIASES.get(key, key)
    return BY_KEY.get(key)


def _stamp() -> str:
    return time.strftime("%Y-%m-%d")


def _clean(text: str) -> str:
    """Yozuvni bitta qatorga keltiradi.

    Ovozdan kelgan matn ba'zan qator uzilishlari bilan keladi; daftarda esa
    har bir yozuv bitta qator bo'lishi kerak, aks holda keyin uni topib
    o'chirish qiyinlashadi.
    """
    return " ".join(str(text).split())[:MAX_ENTRY_CHARS]


def read(note: Note) -> str:
    """Daftar matni. Fayl yo'q bo'lsa — bo'sh satr."""
    try:
        return note.path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError:
        log.exception("Daftarni o'qib bo'lmadi: %s", note.path)
        return ""


def entries(note: Note) -> list[str]:
    """Daftardagi yozuvlar (sarlavha va bo'sh qatorlarsiz)."""
    return [
        line[2:].strip()
        for line in read(note).splitlines()
        if line.startswith("- ")
    ]


def add(note: Note, text: str) -> str:
    """Daftarga yozuv qo'shadi. Takrorini ikkinchi marta yozmaydi."""
    entry = _clean(text)
    if not entry:
        return "Yozuv bo'sh"

    # Bir xil gapni qayta-qayta yozish daftarni ishlatib bo'lmaydigan
    # qiladi. Sanani hisobga olmay solishtiramiz.
    stripped = _strip_date(entry).casefold()
    for existing in entries(note):
        if _strip_date(existing).casefold() == stripped:
            return f"«{note.title}» da bu allaqachon bor"

    try:
        NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
        if not note.path.exists():
            note.path.write_text(f"# {note.title}\n\n", encoding="utf-8")
        with note.path.open("a", encoding="utf-8") as handle:
            handle.write(f"- {_stamp()} — {entry}\n")
    except OSError:
        log.exception("Daftarga yozib bo'lmadi: %s", note.path)
        return "Daftarga yozib bo'lmadi"

    log.info("Daftar «%s»: +1 yozuv", note.key)
    return f"«{note.title}» daftariga yozildi"


_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}\s*[—-]\s*")


def _strip_date(entry: str) -> str:
    return _DATE_PREFIX.sub("", entry).strip()


def remove(note: Note, needle: str) -> str:
    """Matni mos keladigan yozuvni o'chiradi.

    Aynan mos kelishini talab qilmaymiz: yozuv ovozda aytilgan gapdan
    olinadi va uni so'zma-so'z takrorlash amalda imkonsiz.
    """
    target = _clean(needle).casefold()
    if not target:
        return "Nimani o'chirishni ayting"

    lines = read(note).splitlines()
    kept: list[str] = []
    removed = 0
    for line in lines:
        if line.startswith("- ") and target in line.casefold():
            removed += 1
            continue
        kept.append(line)

    if not removed:
        return f"«{note.title}» da bunday yozuv topilmadi"

    try:
        note.path.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    except OSError:
        log.exception("Daftarni yozib bo'lmadi: %s", note.path)
        return "Daftarni yangilab bo'lmadi"
    return f"«{note.title}» dan {removed} ta yozuv o'chirildi"


def context_block() -> str:
    """Barcha daftarlarni tizim ko'rsatmasiga qo'shiladigan matnga yig'adi.

    Bo'sh daftarlar tushirib qoldiriladi — modelga bo'sh sarlavhalarni
    o'qitishning ma'nosi yo'q.
    """
    parts: list[str] = []
    for note in NOTES:
        rows = entries(note)
        if not rows:
            continue
        body = "\n".join(f"- {row}" for row in rows)
        if len(body) > MAX_PROMPT_CHARS:
            # Eng yangilari muhimroq — oxiridan olamiz.
            body = "…\n" + body[-MAX_PROMPT_CHARS:]
        parts.append(f"## {note.title}\n({note.purpose})\n{body}")
    return "\n\n".join(parts)


def summary() -> list[dict[str, object]]:
    """Daftarlar ro'yxati va ularda nechta yozuv borligi."""
    return [
        {
            "daftar": note.key,
            "nom": note.title,
            "yozuvlar": len(entries(note)),
            "fayl": str(note.path),
        }
        for note in NOTES
    ]
