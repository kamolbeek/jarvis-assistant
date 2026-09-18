"""Daftarlar — Jarvis o'zi yozib boradigan matn fayllari.

Talab oddiy edi: «men aytganimni eslab qolsin va qaytib o'sha xatoni
qilmasin». Uni ishonchli qiladigan narsalar esa unchalik oddiy emas:

  * bir xil gapni ikki marta yozmaslik (aks holda daftar ishlatib
    bo'lmaydigan darajada to'lib ketadi);
  * ovozda aytilgan gap bilan o'chira olish (so'zma-so'z takrorlash
    imkonsiz);
  * fayl buzilgan yoki yo'q bo'lsa ham yiqilmaslik.
"""

from __future__ import annotations

import pytest

from jarvis import notebook


@pytest.fixture(autouse=True)
def notebook_dir(tmp_path, monkeypatch):
    """Har bir sinov o'z papkasida ishlasin — haqiqiy daftarga tegmaymiz."""
    monkeypatch.setattr(notebook, "NOTEBOOK_DIR", tmp_path)
    return tmp_path


def _note(key: str = "qoidalar") -> notebook.Note:
    found = notebook.resolve(key)
    assert found is not None
    return found


# --- Yozish va o'qish ---------------------------------------------------------


def test_entry_is_written_and_read_back():
    notebook.add(_note(), "javoblarni qisqa qil")

    assert notebook.entries(_note()) == [
        entry for entry in notebook.entries(_note()) if "qisqa" in entry
    ]
    assert "qisqa" in notebook.entries(_note())[0]


def test_file_gets_a_readable_heading(notebook_dir):
    """Daftar odam o'qiydigan fayl — sarlavhasi bo'lsin."""
    notebook.add(_note("men"), "Toshkentda yashaydi")

    text = (notebook_dir / "men.md").read_text(encoding="utf-8")
    assert text.startswith("# Kamoliddin haqida")
    assert "Toshkentda yashaydi" in text


def test_entry_is_stamped_with_a_date():
    notebook.add(_note(), "ertalab tez javob ber")
    assert notebook.entries(_note())[0][:4].isdigit()


def test_multiline_speech_becomes_one_line():
    """Ovozdan kelgan matn qator uzilishlari bilan kelishi mumkin."""
    notebook.add(_note(), "birinchi qator\nikkinchi qator")

    assert len(notebook.entries(_note())) == 1
    assert "birinchi qator ikkinchi qator" in notebook.entries(_note())[0]


def test_empty_entry_is_refused():
    assert "bo'sh" in notebook.add(_note(), "   ")
    assert notebook.entries(_note()) == []


# --- Takrorlanish -------------------------------------------------------------


def test_the_same_rule_is_not_written_twice():
    """Bir xil gapni qayta-qayta yozish daftarni yaroqsiz qiladi."""
    notebook.add(_note(), "menga «albatta» deb gapirma")
    result = notebook.add(_note(), "menga «albatta» deb gapirma")

    assert "allaqachon bor" in result
    assert len(notebook.entries(_note())) == 1


def test_duplicate_check_ignores_case():
    notebook.add(_note(), "Qisqa gapir")
    notebook.add(_note(), "qisqa gapir")

    assert len(notebook.entries(_note())) == 1


# --- O'chirish ----------------------------------------------------------------


def test_entry_is_removed_by_part_of_its_text():
    """Ovozda aytilgan gap yozuvga aynan mos kelmaydi — qismi yetarli."""
    notebook.add(_note(), "har javobdan keyin xulosa ayt")
    notebook.add(_note(), "ertalab hisobot ber")

    result = notebook.remove(_note(), "xulosa")

    assert "1 ta yozuv o'chirildi" in result
    assert [e for e in notebook.entries(_note()) if "hisobot" in e]
    assert not [e for e in notebook.entries(_note()) if "xulosa" in e]


def test_removing_something_absent_says_so():
    notebook.add(_note(), "bitta qoida")
    assert "topilmadi" in notebook.remove(_note(), "umuman boshqa narsa")


def test_removing_without_text_asks_what():
    assert "ayting" in notebook.remove(_note(), "")


def test_heading_survives_removal(notebook_dir):
    notebook.add(_note(), "o'chiriladigan qoida")
    notebook.remove(_note(), "o'chiriladigan")

    assert (notebook_dir / "qoidalar.md").read_text(encoding="utf-8").startswith("#")


# --- Daftar nomini topish -----------------------------------------------------


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("men", "men"), ("profil", "men"), ("uslub", "men"),
        ("qoidalar", "qoidalar"), ("qoida", "qoidalar"), ("ko'rsatma", "qoidalar"),
        ("xatolar", "xatolar"), ("xato", "xatolar"), ("kamchilik", "xatolar"),
        ("lugat", "lugat"), ("so'z", "lugat"), ("atama", "lugat"),
    ],
)
def test_notebook_name_is_forgiving(said: str, expected: str):
    """Model daftarni turlicha atashi mumkin — ro'yxat qattiq bo'lmasin."""
    found = notebook.resolve(said)
    assert found is not None and found.key == expected


def test_unknown_notebook_is_reported():
    assert notebook.resolve("bunday daftar yo'q") is None


# --- Ko'rsatmaga qo'shish -----------------------------------------------------


def test_context_is_empty_when_nothing_written():
    """Bo'sh sarlavhalarni modelga o'qitishning ma'nosi yo'q."""
    assert notebook.context_block() == ""


def test_context_includes_every_filled_notebook():
    notebook.add(_note("men"), "dasturchi")
    notebook.add(_note("qoidalar"), "qisqa gapir")
    notebook.add(_note("lugat"), "karnaval — ommaviy bayram")

    block = notebook.context_block()

    assert "dasturchi" in block
    assert "qisqa gapir" in block
    assert "karnaval" in block
    # Bo'sh daftar tushib qolsin
    assert "Xatolar va xulosalar" not in block


def test_context_keeps_the_newest_entries_when_long(monkeypatch):
    """Cheksiz o'sgan daftar butun kontekstni yeb qo'ymasligi kerak."""
    monkeypatch.setattr(notebook, "MAX_PROMPT_CHARS", 200)
    for i in range(80):
        notebook.add(_note(), f"qoida raqami {i}")

    block = notebook.context_block()

    assert len(block) < 800
    assert "qoida raqami 79" in block, "eng yangi yozuv qolishi kerak"


# --- Buzilishga chidamlilik ---------------------------------------------------


def test_missing_file_reads_as_empty():
    assert notebook.entries(_note()) == []
    assert notebook.read(_note()) == ""


def test_write_failure_does_not_raise(monkeypatch, tmp_path):
    """Daftar yozilmagani butun javobni yiqitmasligi kerak."""
    blocker = tmp_path / "blocker"
    blocker.write_text("men papka emasman", encoding="utf-8")
    monkeypatch.setattr(notebook, "NOTEBOOK_DIR", blocker / "ichida")

    assert "bo'lmadi" in notebook.add(_note(), "yozilmaydi")


def test_summary_counts_entries():
    notebook.add(_note("men"), "birinchi")
    notebook.add(_note("men"), "ikkinchi")

    rows = {row["daftar"]: row["yozuvlar"] for row in notebook.summary()}

    assert rows["men"] == 2
    assert rows["xatolar"] == 0
