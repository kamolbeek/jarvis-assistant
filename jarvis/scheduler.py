"""Rejalashtiruvchi — Jarvis'ni "so'ralganda javob beradigan" holatdan
"o'zi eslatadigan" holatga o'tkazadigan qism.

Fon rejimida ishlaydi, vaqti kelgan vazifalarni topadi va ularni navbatga qo'yadi.
Asosiy sikl bo'sh bo'lganda navbatni bo'shatadi — Jarvis gap o'rtasida
gapirib yubormasligi uchun.

Jim soatlar (`quiet_hours`) tunda uyg'otmaslik uchun: bu oraliqda eslatmalar
ovozsiz qoladi va ertalab navbatdagi birinchi imkoniyatda aytiladi.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .brain.agenda import Agenda, format_when

log = logging.getLogger("jarvis.scheduler")


@dataclass
class Announcement:
    """Foydalanuvchiga aytiladigan xabar."""

    text: str
    kind: str = "eslatma"       # eslatma | brief
    task_id: int | None = None
    # Bildirishnoma ham ko'rsatilsinmi (kompyuter oldida bo'lmasa foydali)
    notify: bool = True


def _in_quiet_hours(moment: datetime, start_hour: int, end_hour: int) -> bool:
    """Berilgan vaqt jim soatlar ichidami?

    Oraliq yarim tundan o'tishi mumkin (22:00–07:00), shuning uchun ikki holat.
    """
    hour = moment.hour
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


@dataclass
class Scheduler:
    """Vazifalarni kuzatib, vaqti kelganda navbatga qo'yadi."""

    agenda: Agenda
    queue: asyncio.Queue[Announcement]
    check_interval_sec: float = 30.0
    quiet_start: int = 22
    quiet_end: int = 7
    brief_time: str = "08:30"       # bo'sh satr = kunlik brief o'chirilgan
    enabled: bool = True

    _task: asyncio.Task | None = None
    _stop: asyncio.Event = field(default_factory=asyncio.Event)
    _last_brief_date: str = ""
    # Jim soatlarda to'plangan eslatmalar
    _deferred: list[Announcement] = field(default_factory=list)

    # --- Hayot sikli ---

    async def start(self) -> None:
        if not self.enabled:
            log.info("Rejalashtiruvchi o'chirilgan")
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="jarvis-scheduler")
        log.info(
            "Rejalashtiruvchi ishga tushdi (har %.0f s, jim soatlar %02d:00–%02d:00)",
            self.check_interval_sec, self.quiet_start, self.quiet_end,
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # --- Ichki sikl ---

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception:
                # Bitta xato butun rejalashtiruvchini o'ldirmasligi kerak.
                log.exception("Rejalashtiruvchi tsiklida xato")

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.check_interval_sec)
            except asyncio.TimeoutError:
                continue

    async def _tick(self) -> None:
        now = datetime.now()
        quiet = _in_quiet_hours(now, self.quiet_start, self.quiet_end)

        # Jim soatlar tugagan bo'lsa, to'plangan eslatmalarni chiqaramiz.
        if not quiet and self._deferred:
            log.info("Jim soatlar tugadi — %d ta eslatma chiqarilmoqda", len(self._deferred))
            for item in self._deferred:
                await self.queue.put(item)
            self._deferred.clear()

        await self._check_brief(now, quiet)
        await self._check_due_tasks(quiet)

    async def _check_brief(self, now: datetime, quiet: bool) -> None:
        """Kunlik brief vaqti kelganini tekshiradi."""
        if not self.brief_time:
            return
        today = now.strftime("%Y-%m-%d")
        if self._last_brief_date == today:
            return

        try:
            hour, minute = (int(part) for part in self.brief_time.split(":"))
        except ValueError:
            log.warning("brief_time formati noto'g'ri: %r (kutilgan: 08:30)", self.brief_time)
            self.brief_time = ""
            return

        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now < scheduled:
            return

        # Vaqt ancha o'tib ketgan bo'lsa (kompyuter o'chiq edi), brief o'z ma'nosini
        # yo'qotadi — kunni belgilab qo'yamiz-u, o'tkazib yuboramiz.
        if now - scheduled > timedelta(hours=3):
            self._last_brief_date = today
            log.info("Brief vaqti ancha o'tib ketgan, o'tkazib yuborildi")
            return

        self._last_brief_date = today
        announcement = Announcement(text=self.agenda.daily_brief(), kind="brief")
        if quiet:
            self._deferred.append(announcement)
        else:
            await self.queue.put(announcement)

    async def _check_due_tasks(self, quiet: bool) -> None:
        """Vaqti kelgan vazifalarni navbatga qo'yadi."""
        for task in self.agenda.due_tasks(time.time()):
            when = format_when(task.remind_at)
            project = f" ({task.project})" if task.project else ""
            text = f"Eslatma{project}: {task.title}."
            if when and "bugun" not in when:
                text = f"Eslatma{project}: {task.title} — {when}."

            announcement = Announcement(text=text, kind="eslatma", task_id=task.id)

            # Belgilab qo'yamiz: navbatda kutayotganda takroran topilmasin.
            self.agenda.mark_announced(task.id)

            if quiet:
                log.info("Jim soatlar — eslatma keyinga qoldirildi: %s", task.title)
                self._deferred.append(announcement)
            else:
                await self.queue.put(announcement)
                log.info("Eslatma navbatga qo'yildi: %s", task.title)

    # --- Qo'lda chaqirish ---

    async def announce_now(self, text: str, kind: str = "eslatma") -> None:
        """Darhol aytiladigan xabar qo'shadi (asboblar shuni ishlatadi)."""
        await self.queue.put(Announcement(text=text, kind=kind))

    async def request_brief(self) -> None:
        """Kunlik briefni hoziroq aytadi."""
        await self.queue.put(Announcement(text=self.agenda.daily_brief(), kind="brief"))
