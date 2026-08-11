"""Ma'lumot qayerda saqlanadi va eskisidan qanday ko'chadi.

Bu modulning butun ma'nosi bitta jumlada: **foydalanuvchi ma'lumoti
yo'qolmasligi kerak.** Shuning uchun bu yerdagi testlar asosan yo'q qilib
bo'lmasligini tekshiradi — nusxa olinadi, ustiga yozilmaydi, eskisi joyida
qoladi.

Ilgari fayllar uch xil yashirin joyga tarqalgan edi (`~/.jarvis`,
`~/jarvis-workspace`, repo ichi). Endi bitta ko'rinadigan papka:
`~/Documents/Jarvis`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.config import (
    EXAMPLE_CONFIG_PATH,
    jarvis_home,
    load_config,
    user_config_path,
)
from jarvis.migrate import has_content, migrate


def shipped_config():
    """Faqat repo bilan keladigan asos — mashinadagi shaxsiy sozlamasiz.

    Aks holda test ishlab turgan kompyuterdagi `jarvis.yaml` ga bog'liq
    bo'lib qolardi.
    """
    return load_config(path=EXAMPLE_CONFIG_PATH)


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """Sinov uchun vaqtinchalik ma'lumotlar papkasi."""
    target = tmp_path / "Jarvis"
    monkeypatch.setenv("JARVIS_HOME", str(target))
    return target.resolve()


# --------------------------------------------------------------- papka tanlash


def test_default_home_is_documents_jarvis(monkeypatch):
    """Standart joy — Hujjatlar ichida, ko'rinadigan papka."""
    monkeypatch.delenv("JARVIS_HOME", raising=False)
    assert jarvis_home() == Path.home() / "Documents" / "Jarvis"


def test_env_overrides_home(home):
    """Bitta o'zgaruvchi butun tizimni ko'chiradi."""
    assert jarvis_home() == home


def test_blank_env_falls_back_to_default(monkeypatch):
    """Bo'sh qiymat "sozlanmagan" degani — ildizga yozib yubormaslik kerak."""
    monkeypatch.setenv("JARVIS_HOME", "   ")
    assert jarvis_home() == Path.home() / "Documents" / "Jarvis"


# ------------------------------------------------------------------ yo'llar


def test_all_paths_live_under_home(home):
    """Xotira, audit va ish papkasi — hammasi bitta papka ichida.

    Aynan shu narsa ilgari buzilgan edi: uchtasi uch joyda edi.
    """
    cfg = shipped_config()
    for path in (cfg.memory_path, cfg.audit_log, cfg.workspace, cfg.logs_dir):
        assert home in path.parents or path.parent == home, path


def test_ensure_dirs_creates_everything(home):
    cfg = shipped_config()
    cfg.ensure_dirs()
    for path in (home, cfg.workspace, cfg.logs_dir, cfg.wakewords_dir, cfg.ui_state_dir):
        assert path.is_dir(), path


def test_writable_roots_stay_inside_home(home):
    """Jarvis faqat o'z papkasiga yozadi.

    Foydalanuvchining Hujjatlar papkasida boshqa loyihalari bor — noto'g'ri
    tushunilgan bitta buyruq ularga tegib ketmasligi kerak.
    """
    cfg = shipped_config()
    for root in cfg.writable_roots():
        assert home in root.parents or root == home, root


def test_home_config_wins_over_repo(home, tmp_path):
    """Sozlama ikki joyda bo'lsa, ma'lumotlar papkasidagisi ustun."""
    home.mkdir(parents=True)
    (home / "jarvis.yaml").write_text(
        'identity:\n  user_name: "Kamoliddin"\n', encoding="utf-8"
    )
    assert load_config().get("identity.user_name") == "Kamoliddin"
    assert user_config_path() == home / "jarvis.yaml"


# ---------------------------------------------------------------- ko'chirish


@pytest.fixture
def legacy(tmp_path, monkeypatch) -> Path:
    """Eski tarqoq joylarni taqlid qiladi."""
    fake_home = tmp_path / "uy"
    (fake_home / ".jarvis").mkdir(parents=True)
    (fake_home / ".jarvis" / "memory.db").write_text("eski xotira", encoding="utf-8")
    (fake_home / ".jarvis" / "audit.log").write_text("eski jurnal", encoding="utf-8")
    (fake_home / "jarvis-workspace").mkdir()
    (fake_home / "jarvis-workspace" / "hisobot.md").write_text("ish", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    return fake_home


def test_migrate_copies_legacy_data(legacy, tmp_path):
    home = tmp_path / "Jarvis"
    moved = migrate(home, tmp_path / "repo")

    assert (home / "memory.db").read_text(encoding="utf-8") == "eski xotira"
    assert (home / "audit.log").read_text(encoding="utf-8") == "eski jurnal"
    assert (home / "workspace" / "hisobot.md").read_text(encoding="utf-8") == "ish"
    assert len(moved) == 3


def test_migrate_never_deletes_the_original(legacy, tmp_path):
    """Nusxa olinadi, ko'chirilmaydi — biror narsa noto'g'ri ketsa qaytish uchun."""
    migrate(tmp_path / "Jarvis", tmp_path / "repo")
    assert (legacy / ".jarvis" / "memory.db").exists()
    assert (legacy / "jarvis-workspace" / "hisobot.md").exists()


def test_migrate_never_overwrites(legacy, tmp_path):
    """Asosiy himoya: manzilda ma'lumot bo'lsa, unga tegilmaydi."""
    home = tmp_path / "Jarvis"
    home.mkdir()
    (home / "memory.db").write_text("YANGI xotira", encoding="utf-8")

    migrate(home, tmp_path / "repo")

    assert (home / "memory.db").read_text(encoding="utf-8") == "YANGI xotira"


def test_migrate_is_idempotent(legacy, tmp_path):
    """Ikkinchi marta chaqirilganda ish qolmaydi."""
    home = tmp_path / "Jarvis"
    assert migrate(home, tmp_path / "repo")
    assert migrate(home, tmp_path / "repo") == []


def test_migrate_ignores_empty_source(legacy, tmp_path):
    """Bo'sh papka ko'chiriladigan ma'lumot emas."""
    (legacy / ".jarvis" / "wakewords").mkdir()
    moved = migrate(tmp_path / "Jarvis", tmp_path / "repo")
    assert not any("uyg'otuvchi" in line for line in moved)


def test_empty_target_dir_does_not_block_migration(legacy, tmp_path):
    """Avtomatik yaratilgan bo'sh papka ko'chirishni to'smasligi kerak.

    `ensure_dirs()` papkalarni oldindan yaratib qo'yishi mumkin — o'shanda
    ham ish papkasidagi fayllar ko'chib o'tishi shart.
    """
    home = tmp_path / "Jarvis"
    (home / "workspace").mkdir(parents=True)

    migrate(home, tmp_path / "repo")

    assert (home / "workspace" / "hisobot.md").exists()


def test_env_file_is_never_copied_automatically(legacy, tmp_path):
    """Kalitlarni so'ramasdan ikkinchi joyga nusxalamaymiz."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-maxfiy", encoding="utf-8")

    migrate(tmp_path / "Jarvis", repo)

    assert not (tmp_path / "Jarvis" / ".env").exists()


# ------------------------------------------------------------------ yordamchi


@pytest.mark.parametrize(
    "make, expected",
    [
        (lambda p: None, False),                              # umuman yo'q
        (lambda p: p.mkdir(), False),                         # bo'sh papka
        (lambda p: p.write_text("", encoding="utf-8"), False),  # bo'sh fayl
        (lambda p: p.write_text("bor", encoding="utf-8"), True),
    ],
)
def test_has_content(tmp_path, make, expected):
    path = tmp_path / "narsa"
    make(path)
    assert has_content(path) is expected
