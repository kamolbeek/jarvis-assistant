"""Eski joylardagi ma'lumotni bitta uyga yig'ish.

Ilgari Jarvis o'z fayllarini uch xil joyga tarqatardi:

    ~/.jarvis/          xotira bazasi, audit jurnali, loglar
    ~/jarvis-workspace/ fayl va kod ishlari
    config/jarvis.yaml  sozlama — repo ichida

Uchtasining ham kamchiligi bir xil: foydalanuvchi ularni ko'rmaydi,
zaxira nusxaga qo'shmaydi, repo o'chirilsa esa sozlama yo'qoladi.
Endi hammasi `~/Documents/Jarvis` da — ko'rinadigan, bitta papkada.

Bu modul eskisidan yangisiga o'tishni bajaradi. Bitta qat'iy qoida bor:

    **Hech narsa o'chirilmaydi va hech narsaning ustiga yozilmaydi.**

Fayllar NUSXALANADI, eskisi joyida qoladi. Nusxa faqat manzilda hali
hech narsa bo'lmaganda olinadi. Shuning uchun buni necha marta ishga
tushirsangiz ham natija bir xil, va noto'g'ri ketgan taqdirda ham
eski nusxangiz joyida turadi.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("jarvis.migrate")


@dataclass(frozen=True)
class Move:
    """Bitta ko'chirish: qayerdan, qayerga, nima deb atash."""

    source: Path
    target_name: str
    label: str


def legacy_moves(repo_root: Path, home: Path) -> list[Move]:
    """Eski joylar ro'yxati. `home` — yangi ildiz papka."""
    old = Path.home() / ".jarvis"
    return [
        Move(old / "memory.db", "memory.db", "xotira bazasi"),
        Move(old / "audit.log", "audit.log", "audit jurnali"),
        Move(old / "logs", "logs", "jurnallar"),
        Move(old / "wakewords", "wakewords", "uyg'otuvchi so'z modellari"),
        Move(Path.home() / "jarvis-workspace", "workspace", "ish papkasi"),
        Move(repo_root / "config" / "jarvis.yaml", "jarvis.yaml", "sozlama"),
    ]
    # `.env` ataylab yo'q: unda API kalitlaringiz bor va ularni so'ramasdan
    # ikkinchi joyga nusxalash noto'g'ri bo'lardi. `jarvis doctor` buni
    # ko'rsatadi va ko'chirishni o'zingizga taklif qiladi.


def has_content(path: Path) -> bool:
    """Yo'lda haqiqatan biror narsa bormi?

    Bo'sh papka va bo'sh fayl "yo'q" deb hisoblanadi — aks holda
    avtomatik yaratilgan bo'sh papka ko'chirishni to'sib qo'yardi.
    """
    try:
        if not path.exists():
            return False
        if path.is_dir():
            return any(path.iterdir())
        return path.stat().st_size > 0
    except OSError:
        # O'qib bo'lmasa, tegmaganimiz ma'qul.
        return False


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)


def migrate(home: Path, repo_root: Path) -> list[str]:
    """Eski ma'lumotni `home` ga nusxalaydi.

    Qaytaradi: nima ko'chirilgani haqidagi qatorlar (bo'sh bo'lsa — ish yo'q).
    Xato bo'lsa ham ishlashda davom etadi: bitta fayl ko'chmagani uchun
    Jarvis ishga tushmay qolishi noto'g'ri bo'lardi.
    """
    done: list[str] = []

    for move in legacy_moves(repo_root, home):
        target = home / move.target_name

        if not has_content(move.source):
            continue
        if has_content(target):
            # Manzilda allaqachon bor — tegmaymiz. Bu asosiy himoya:
            # yangi ma'lumot eskisi bilan almashib ketmaydi.
            continue

        try:
            _copy(move.source, target)
        except OSError as exc:
            log.warning("Ko'chirib bo'lmadi (%s): %s", move.label, exc)
            continue

        done.append(f"{move.label}: {move.source} → {target}")
        log.info("Ko'chirildi — %s: %s → %s", move.label, move.source, target)

    return done


def migrate_default() -> list[str]:
    """Standart yo'llar bilan ko'chirish (dastur ishga tushganda chaqiriladi)."""
    from .config import REPO_ROOT, jarvis_home

    home = jarvis_home()
    home.mkdir(parents=True, exist_ok=True)
    return migrate(home, REPO_ROOT)


def leftovers(repo_root: Path) -> list[Path]:
    """Ko'chirilgandan keyin ham eski joyda turgan narsalar.

    Ularni Jarvis o'chirmaydi — bu foydalanuvchining qaroriga qoldiriladi.
    `jarvis doctor` shu ro'yxatni ko'rsatadi.
    """
    candidates = [
        Path.home() / ".jarvis",
        Path.home() / "jarvis-workspace",
        repo_root / "config" / "jarvis.yaml",
    ]
    return [path for path in candidates if has_content(path)]
