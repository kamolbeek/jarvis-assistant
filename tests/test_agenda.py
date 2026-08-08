"""Agenda, rejalashtiruvchi va telefon ko'prigi testlari."""

from __future__ import annotations

import asyncio
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from jarvis.brain.agenda import (
    Agenda,
    format_when,
    next_occurrence,
    parse_when,
)
from jarvis.bus import EventBus
from jarvis.scheduler import Announcement, Scheduler, _in_quiet_hours
from jarvis.ui.server import UiServer, base64_to_pcm, pcm_to_base64


@pytest.fixture
def agenda():
    with tempfile.TemporaryDirectory() as tmp:
        instance = Agenda(Path(tmp) / "a.db")
        yield instance
        instance.close()


# ---------------------------------------------------------------- Vaqt


def test_parse_when_formats():
    assert parse_when("2026-08-09T10:00") == datetime(2026, 8, 9, 10, 0).timestamp()
    assert parse_when("2026-08-09 10:00") == datetime(2026, 8, 9, 10, 0).timestamp()
    assert parse_when("2026-08-09") == datetime(2026, 8, 9).timestamp()
    assert parse_when("") is None
    assert parse_when(None) is None


def test_parse_when_rejects_garbage():
    with pytest.raises(ValueError, match="Vaqtni tushunmadim"):
        parse_when("ertaga soat 10 da")


def test_format_when_uses_relative_days():
    now = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)
    assert format_when(now.timestamp()).startswith("bugun")
    assert format_when((now + timedelta(days=1)).timestamp()).startswith("ertaga")
    assert format_when((now - timedelta(days=1)).timestamp()).startswith("kecha")
    # Uzoq sana — to'liq format
    assert "." in format_when((now + timedelta(days=10)).timestamp())


def test_format_when_omits_midnight_time():
    midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    assert "soat" not in format_when(midnight.timestamp())


@pytest.mark.parametrize(
    ("repeat", "days"),
    [("kunlik", 1), ("haftalik", 7)],
)
def test_next_occurrence_simple(repeat: str, days: int):
    start = datetime(2026, 8, 10, 9, 0)  # dushanba
    following = next_occurrence(start.timestamp(), repeat)
    assert following == (start + timedelta(days=days)).timestamp()


def test_next_occurrence_skips_weekend():
    friday = datetime(2026, 8, 14, 9, 0)
    assert friday.weekday() == 4, "test sanasi juma bo'lishi kerak"

    following = datetime.fromtimestamp(next_occurrence(friday.timestamp(), "ish_kunlari"))
    assert following.weekday() == 0, "jumadan keyingi ish kuni dushanba bo'lishi kerak"
    assert following.hour == 9


def test_next_occurrence_none_without_repeat():
    assert next_occurrence(time.time(), "") is None


# ---------------------------------------------------------------- Loyihalar


def test_project_create_and_update(agenda: Agenda):
    agenda.upsert_project("iLevel", description="ERP tizimi", next_step="hisobot moduli")
    project = agenda.get_project("iLevel")
    assert project is not None
    assert project.status == "faol"
    assert project.next_step == "hisobot moduli"

    # Faqat bitta maydonni yangilash qolganini o'chirmasligi kerak
    agenda.upsert_project("iLevel", status="kutilmoqda")
    project = agenda.get_project("iLevel")
    assert project.status == "kutilmoqda"
    assert project.description == "ERP tizimi", "tavsif saqlanib qolishi kerak"
    assert len(agenda.list_projects()) == 1


def test_project_rejects_unknown_status(agenda: Agenda):
    with pytest.raises(ValueError, match="Noma'lum holat"):
        agenda.upsert_project("X", status="allakachon")


def test_project_list_orders_active_first(agenda: Agenda):
    agenda.upsert_project("Tugagan", status="tugagan")
    agenda.upsert_project("Faol", status="faol")
    assert [p.name for p in agenda.list_projects()][0] == "Faol"


# ---------------------------------------------------------------- Vazifalar


def test_task_creates_missing_project(agenda: Agenda):
    task = agenda.add_task("Hisobotni yuborish", project="Yangi loyiha")
    assert task.project == "Yangi loyiha"
    assert agenda.get_project("Yangi loyiha") is not None


def test_task_rejects_unknown_repeat(agenda: Agenda):
    with pytest.raises(ValueError, match="Noma'lum takror"):
        agenda.add_task("X", repeat="har_soatda")


def test_completing_repeating_task_schedules_next(agenda: Agenda):
    when = datetime(2026, 8, 10, 9, 0).timestamp()
    task = agenda.add_task("Kunlik hisobot", remind_at=when, repeat="kunlik")

    agenda.complete_task(task.id)
    pending = agenda.list_tasks()

    assert len(pending) == 1, "takrorlanuvchi vazifa keyingi kunga ko'chishi kerak"
    assert pending[0].title == "Kunlik hisobot"
    assert pending[0].remind_at == when + 86400


def test_completing_plain_task_leaves_nothing(agenda: Agenda):
    task = agenda.add_task("Bir martalik", remind_at=time.time())
    agenda.complete_task(task.id)
    assert agenda.list_tasks() == []


def test_due_tasks_only_returns_ripe_and_unannounced(agenda: Agenda):
    now = time.time()
    past = agenda.add_task("O'tgan", remind_at=now - 60)
    agenda.add_task("Kelajak", remind_at=now + 3600)
    agenda.add_task("Vaqtsiz")

    due = agenda.due_tasks(now)
    assert [t.title for t in due] == ["O'tgan"]

    # Aytilgandan keyin qayta chiqmasligi kerak
    agenda.mark_announced(past.id)
    assert agenda.due_tasks(now) == []


def test_tasks_for_day_filters_to_today(agenda: Agenda):
    today = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
    agenda.add_task("Bugungi", remind_at=today.timestamp())
    agenda.add_task("Ertangi", remind_at=(today + timedelta(days=1)).timestamp())

    assert [t.title for t in agenda.tasks_for_day()] == ["Bugungi"]


def test_daily_brief_mentions_counts(agenda: Agenda):
    today = datetime.now().replace(hour=11, minute=0, second=0, microsecond=0)
    agenda.add_task("Uchrashuv", remind_at=today.timestamp())
    agenda.upsert_project("iLevel")

    brief = agenda.daily_brief()
    assert "1 ta ish" in brief
    assert "iLevel" in brief


def test_daily_brief_when_empty(agenda: Agenda):
    assert "yo'q" in agenda.daily_brief()


# ---------------------------------------------------------------- Aloqalar


def test_contact_exact_and_partial_match(agenda: Agenda):
    agenda.upsert_contact("Alisher Karimov", telegram="123456", phone="+998901234567")

    assert agenda.find_contact("Alisher Karimov")["telegram"] == "123456"
    assert agenda.find_contact("alisher karimov")["telegram"] == "123456"
    assert agenda.find_contact("Alisher")["telegram"] == "123456", "qisman moslik ishlashi kerak"


def test_contact_ambiguous_partial_returns_none(agenda: Agenda):
    """Ikki odam mos kelsa, taxmin qilib noto'g'ri odamga yozib yubormasligi kerak."""
    agenda.upsert_contact("Alisher Karimov", telegram="1")
    agenda.upsert_contact("Alisher Toshmatov", telegram="2")
    assert agenda.find_contact("Alisher") is None


def test_contact_update_keeps_existing_fields(agenda: Agenda):
    agenda.upsert_contact("Bobur", telegram="111", phone="+998901111111")
    agenda.upsert_contact("Bobur", telegram="222")

    contact = agenda.find_contact("Bobur")
    assert contact["telegram"] == "222"
    assert contact["telefon"] == "+998901111111", "bo'sh maydon mavjudini o'chirmasligi kerak"


def test_contact_missing_returns_none(agenda: Agenda):
    assert agenda.find_contact("Yo'q odam") is None


# ---------------------------------------------------------------- Rejalashtiruvchi


@pytest.mark.parametrize(
    ("hour", "expected"),
    [(23, True), (2, True), (6, True), (7, False), (12, False), (21, False), (22, True)],
)
def test_quiet_hours_across_midnight(hour: int, expected: bool):
    moment = datetime(2026, 8, 10, hour, 0)
    assert _in_quiet_hours(moment, 22, 7) is expected


@pytest.mark.parametrize(
    ("hour", "expected"),
    [(10, True), (13, True), (9, False), (15, False)],
)
def test_quiet_hours_same_day_range(hour: int, expected: bool):
    assert _in_quiet_hours(datetime(2026, 8, 10, hour, 0), 10, 14) is expected


def test_quiet_hours_disabled_when_equal():
    assert _in_quiet_hours(datetime(2026, 8, 10, 3, 0), 0, 0) is False


async def test_scheduler_queues_due_task(agenda: Agenda):
    agenda.add_task("Uchrashuv", remind_at=time.time() - 10)
    queue: asyncio.Queue[Announcement] = asyncio.Queue()
    scheduler = Scheduler(agenda=agenda, queue=queue, brief_time="")

    await scheduler._check_due_tasks(quiet=False)

    assert queue.qsize() == 1
    assert "Uchrashuv" in queue.get_nowait().text
    # Ikkinchi marta chaqirilganda takrorlanmasligi kerak
    await scheduler._check_due_tasks(quiet=False)
    assert queue.empty()


async def test_scheduler_defers_during_quiet_hours(agenda: Agenda):
    agenda.add_task("Tungi eslatma", remind_at=time.time() - 10)
    queue: asyncio.Queue[Announcement] = asyncio.Queue()
    # quiet_start == quiet_end => jim soatlar o'chirilgan, `_tick` ularni chiqaradi
    scheduler = Scheduler(agenda=agenda, queue=queue, brief_time="",
                          quiet_start=0, quiet_end=0)

    await scheduler._check_due_tasks(quiet=True)
    assert queue.empty(), "jim soatlarda uyg'otmasligi kerak"
    assert len(scheduler._deferred) == 1

    # Jim soatlar tugagach navbatdagi tekshiruv ularni chiqarishi kerak
    await scheduler._tick()

    assert queue.qsize() == 1
    assert "Tungi eslatma" in queue.get_nowait().text
    assert scheduler._deferred == []


async def test_scheduler_survives_broken_agenda():
    """Bitta xato butun rejalashtiruvchini o'ldirmasligi kerak."""

    class Broken:
        def due_tasks(self, now=None):
            raise RuntimeError("baza yiqildi")

        def daily_brief(self):
            return ""

    queue: asyncio.Queue[Announcement] = asyncio.Queue()
    scheduler = Scheduler(agenda=Broken(), queue=queue, brief_time="",
                          check_interval_sec=0.01)
    await scheduler.start()
    await asyncio.sleep(0.05)
    running = scheduler._task is not None and not scheduler._task.done()
    await scheduler.stop()

    assert running, "xatodan keyin ham ishlashda davom etishi kerak"


# ---------------------------------------------------------------- Telefon ko'prigi


def test_pcm_base64_roundtrip():
    original = np.array([0, 1000, -1000, 32767, -32768], dtype=np.int16)
    restored = base64_to_pcm(pcm_to_base64(original))
    assert np.array_equal(original, restored)


def test_pcm_base64_handles_odd_bytes():
    """Toq bayt kelsa yiqilmasligi, oxirgi yarim namunani tashlashi kerak."""
    import base64 as b64

    odd = b64.b64encode(b"\x01\x02\x03").decode()
    assert base64_to_pcm(odd).size == 1


def test_server_requires_token_when_exposed():
    """Tarmoqqa ochilgan server tokensiz ishga tushmasligi kerak."""
    with pytest.raises(RuntimeError, match="token"):
        UiServer(EventBus(), host="0.0.0.0", port=8765, token="")


def test_server_allows_loopback_without_token():
    server = UiServer(EventBus(), host="127.0.0.1", port=8765)
    assert server._token_ok("/") is True


def test_server_checks_token_in_query():
    server = UiServer(EventBus(), host="0.0.0.0", port=8765, token="maxfiy")
    assert server._token_ok("/?t=maxfiy") is True
    assert server._token_ok("/?t=boshqa") is False
    assert server._token_ok("/") is False
    assert server._token_ok("/?t=maxfiy&x=1") is True


def test_phone_url_includes_token():
    server = UiServer(EventBus(), host="0.0.0.0", port=8765, token="abc")
    assert server.phone_url() == "http://0.0.0.0:8765/?t=abc"
