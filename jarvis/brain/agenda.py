"""Loyihalar, vazifalar va aloqalar — Jarvis'ni "eslatuvchi" emas, "yordamchi" qiladigan qism.

Farqi shunda: eslatuvchi siz so'raganda javob beradi, yordamchi esa **o'zi** aytadi.
Shu sababli har bir vazifada `remind_at` bor va rejalashtiruvchi (scheduler) uni
kuzatib turadi — vaqti kelganda Jarvis o'zi gapiradi.

Xotira bilan bitta SQLite faylni bo'lishadi, lekin jadvallar alohida: xotira
"nima bilaman" bo'lsa, bu yerda "nima qilish kerak" saqlanadi.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("jarvis.brain.agenda")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'faol',
    description TEXT NOT NULL DEFAULT '',
    next_step   TEXT NOT NULL DEFAULT '',
    deadline    REAL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    title       TEXT NOT NULL,
    due_at      REAL,
    remind_at   REAL,
    repeat      TEXT NOT NULL DEFAULT '',
    done        INTEGER NOT NULL DEFAULT 0,
    announced   INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    name        TEXT PRIMARY KEY,
    telegram    TEXT NOT NULL DEFAULT '',
    phone       TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_tasks_remind ON tasks(done, announced, remind_at);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id, done);
"""

# `repeat` uchun ruxsat etilgan qiymatlar.
REPEATS = {"", "kunlik", "ish_kunlari", "haftalik", "oylik"}

STATUSES = {"faol", "kutilmoqda", "tugagan", "to'xtatilgan"}


@dataclass
class Project:
    id: int
    name: str
    status: str
    description: str
    next_step: str
    deadline: float | None
    updated_at: float


@dataclass
class Task:
    id: int
    title: str
    project: str | None
    due_at: float | None
    remind_at: float | None
    repeat: str
    done: bool


def parse_when(value: str | None) -> float | None:
    """`2026-08-09T10:00` yoki `2026-08-09 10:00` ni timestamp'ga aylantiradi."""
    if not value:
        return None
    text = str(value).strip().replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(f"Vaqtni tushunmadim: {value!r}. Format: 2026-08-09T10:00")


def format_when(stamp: float | None) -> str:
    """Timestamp'ni o'zbekcha o'qiladigan matnga aylantiradi."""
    if stamp is None:
        return ""
    moment = datetime.fromtimestamp(stamp)
    today = datetime.now().date()
    delta_days = (moment.date() - today).days

    if delta_days == 0:
        prefix = "bugun"
    elif delta_days == 1:
        prefix = "ertaga"
    elif delta_days == -1:
        prefix = "kecha"
    else:
        prefix = moment.strftime("%d.%m.%Y")

    if moment.hour == 0 and moment.minute == 0:
        return prefix
    return f"{prefix} soat {moment.strftime('%H:%M')}"


def next_occurrence(stamp: float, repeat: str) -> float | None:
    """Takrorlanuvchi vazifaning keyingi vaqtini hisoblaydi."""
    moment = datetime.fromtimestamp(stamp)

    if repeat == "kunlik":
        return (moment + timedelta(days=1)).timestamp()
    if repeat == "haftalik":
        return (moment + timedelta(weeks=1)).timestamp()
    if repeat == "oylik":
        # Oy uzunligi har xil — 28 kundan keyin o'sha kunga eng yaqinini olamiz.
        month = moment.month % 12 + 1
        year = moment.year + (1 if moment.month == 12 else 0)
        day = min(moment.day, 28)
        return moment.replace(year=year, month=month, day=day).timestamp()
    if repeat == "ish_kunlari":
        nxt = moment + timedelta(days=1)
        while nxt.weekday() >= 5:  # 5=shanba, 6=yakshanba
            nxt += timedelta(days=1)
        return nxt.timestamp()
    return None


class Agenda:
    """Loyihalar, vazifalar va aloqalar ombori."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- Loyihalar ---

    def upsert_project(
        self,
        name: str,
        *,
        status: str | None = None,
        description: str | None = None,
        next_step: str | None = None,
        deadline: float | None = None,
    ) -> Project:
        """Loyihani yaratadi yoki mavjudini yangilaydi (berilgan maydonlarni)."""
        if status is not None and status not in STATUSES:
            raise ValueError(f"Noma'lum holat: {status}. Mumkin: {', '.join(sorted(STATUSES))}")

        now = time.time()
        existing = self.get_project(name)

        if existing is None:
            self._conn.execute(
                "INSERT INTO projects(name, status, description, next_step, deadline, "
                "created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (name, status or "faol", description or "", next_step or "", deadline, now, now),
            )
        else:
            self._conn.execute(
                "UPDATE projects SET status = COALESCE(?, status), "
                "description = COALESCE(?, description), next_step = COALESCE(?, next_step), "
                "deadline = COALESCE(?, deadline), updated_at = ? WHERE name = ?",
                (status, description, next_step, deadline, now, name),
            )
        self._conn.commit()
        project = self.get_project(name)
        assert project is not None
        return project

    def get_project(self, name: str) -> Project | None:
        row = self._conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        return self._to_project(row) if row else None

    def list_projects(self, status: str | None = None) -> list[Project]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC", (status,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM projects ORDER BY "
                # Faol loyihalar birinchi, tugaganlari oxirida
                "CASE status WHEN 'faol' THEN 0 WHEN 'kutilmoqda' THEN 1 ELSE 2 END, "
                "updated_at DESC"
            ).fetchall()
        return [self._to_project(row) for row in rows]

    @staticmethod
    def _to_project(row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            status=row["status"],
            description=row["description"],
            next_step=row["next_step"],
            deadline=row["deadline"],
            updated_at=row["updated_at"],
        )

    # --- Vazifalar ---

    def add_task(
        self,
        title: str,
        *,
        project: str | None = None,
        due_at: float | None = None,
        remind_at: float | None = None,
        repeat: str = "",
    ) -> Task:
        if repeat not in REPEATS:
            raise ValueError(f"Noma'lum takror: {repeat}. Mumkin: {', '.join(sorted(REPEATS - {''}))}")

        project_id = None
        if project:
            found = self.get_project(project)
            if found is None:
                found = self.upsert_project(project)
            project_id = found.id

        # Vaqt berilgan-u eslatma berilmagan bo'lsa, o'sha vaqtda eslatamiz.
        if remind_at is None and due_at is not None:
            remind_at = due_at

        cursor = self._conn.execute(
            "INSERT INTO tasks(project_id, title, due_at, remind_at, repeat, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (project_id, title, due_at, remind_at, repeat, time.time()),
        )
        self._conn.commit()
        task = self.get_task(int(cursor.lastrowid))
        assert task is not None
        return task

    def get_task(self, task_id: int) -> Task | None:
        row = self._conn.execute(
            "SELECT t.*, p.name AS project_name FROM tasks t "
            "LEFT JOIN projects p ON p.id = t.project_id WHERE t.id = ?",
            (task_id,),
        ).fetchone()
        return self._to_task(row) if row else None

    def complete_task(self, task_id: int) -> Task | None:
        """Vazifani bajarilgan deb belgilaydi. Takrorlanuvchi bo'lsa, keyingisini yaratadi."""
        task = self.get_task(task_id)
        if task is None:
            return None

        self._conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        self._conn.commit()

        if task.repeat and task.remind_at:
            following = next_occurrence(task.remind_at, task.repeat)
            if following is not None:
                shift = following - task.remind_at
                self.add_task(
                    task.title,
                    project=task.project,
                    due_at=(task.due_at + shift) if task.due_at else None,
                    remind_at=following,
                    repeat=task.repeat,
                )
        return task

    def list_tasks(
        self, *, project: str | None = None, include_done: bool = False, limit: int = 50
    ) -> list[Task]:
        clauses = []
        params: list[object] = []
        if not include_done:
            clauses.append("t.done = 0")
        if project:
            clauses.append("p.name = ?")
            params.append(project)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        rows = self._conn.execute(
            f"SELECT t.*, p.name AS project_name FROM tasks t "
            f"LEFT JOIN projects p ON p.id = t.project_id {where} "
            # Vaqti belgilanganlar birinchi, keyin yaqinligi bo'yicha
            f"ORDER BY t.remind_at IS NULL, t.remind_at ASC LIMIT ?",
            params,
        ).fetchall()
        return [self._to_task(row) for row in rows]

    def tasks_for_day(self, day: datetime | None = None) -> list[Task]:
        """Bir kunlik vazifalar — kunlik brief uchun."""
        target = (day or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
        start = target.timestamp()
        end = (target + timedelta(days=1)).timestamp()

        rows = self._conn.execute(
            "SELECT t.*, p.name AS project_name FROM tasks t "
            "LEFT JOIN projects p ON p.id = t.project_id "
            "WHERE t.done = 0 AND t.remind_at >= ? AND t.remind_at < ? "
            "ORDER BY t.remind_at ASC",
            (start, end),
        ).fetchall()
        return [self._to_task(row) for row in rows]

    def due_tasks(self, now: float | None = None) -> list[Task]:
        """Vaqti kelgan, hali aytilmagan vazifalar."""
        moment = now if now is not None else time.time()
        rows = self._conn.execute(
            "SELECT t.*, p.name AS project_name FROM tasks t "
            "LEFT JOIN projects p ON p.id = t.project_id "
            "WHERE t.done = 0 AND t.announced = 0 AND t.remind_at IS NOT NULL "
            "AND t.remind_at <= ? ORDER BY t.remind_at ASC",
            (moment,),
        ).fetchall()
        return [self._to_task(row) for row in rows]

    def mark_announced(self, task_id: int) -> None:
        """Vazifa aytildi — qayta aytilmasin."""
        self._conn.execute("UPDATE tasks SET announced = 1 WHERE id = ?", (task_id,))
        self._conn.commit()

    def delete_task(self, task_id: int) -> bool:
        cursor = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _to_task(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            project=row["project_name"],
            due_at=row["due_at"],
            remind_at=row["remind_at"],
            repeat=row["repeat"],
            done=bool(row["done"]),
        )

    # --- Aloqalar ---

    def upsert_contact(
        self, name: str, *, telegram: str = "", phone: str = "", note: str = ""
    ) -> None:
        """Aloqani saqlaydi. Bo'sh maydonlar mavjud qiymatni o'chirmaydi."""
        self._conn.execute(
            "INSERT INTO contacts(name, telegram, phone, note) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET "
            "telegram = CASE WHEN excluded.telegram != '' THEN excluded.telegram "
            "               ELSE contacts.telegram END, "
            "phone = CASE WHEN excluded.phone != '' THEN excluded.phone "
            "            ELSE contacts.phone END, "
            "note = CASE WHEN excluded.note != '' THEN excluded.note ELSE contacts.note END",
            (name, telegram, phone, note),
        )
        self._conn.commit()

    def find_contact(self, name: str) -> dict[str, str] | None:
        """Aloqani nomi bo'yicha topadi (katta-kichik harf va qisman moslik bilan)."""
        row = self._conn.execute(
            "SELECT * FROM contacts WHERE lower(name) = lower(?)", (name,)
        ).fetchone()
        if row is None:
            # Qisman moslik: "Alisher" -> "Alisher Karimov"
            row = self._conn.execute(
                "SELECT * FROM contacts WHERE lower(name) LIKE lower(?) LIMIT 2",
                (f"%{name}%",),
            ).fetchall()
            if len(row) != 1:
                return None  # Topilmadi yoki noaniq — taxmin qilmaymiz
            row = row[0]
        return {
            "nom": row["name"],
            "telegram": row["telegram"],
            "telefon": row["phone"],
            "izoh": row["note"],
        }

    def list_contacts(self) -> list[dict[str, str]]:
        rows = self._conn.execute("SELECT * FROM contacts ORDER BY name").fetchall()
        return [
            {"nom": r["name"], "telegram": r["telegram"], "telefon": r["phone"], "izoh": r["note"]}
            for r in rows
        ]

    def delete_contact(self, name: str) -> bool:
        cursor = self._conn.execute("DELETE FROM contacts WHERE lower(name) = lower(?)", (name,))
        self._conn.commit()
        return cursor.rowcount > 0

    # --- Brief ---

    def daily_brief(self) -> str:
        """Kun boshidagi qisqa xulosa — ovozda aytish uchun."""
        tasks = self.tasks_for_day()
        projects = [p for p in self.list_projects("faol")]

        if not tasks and not projects:
            return "Bugunga rejalashtirilgan ish yo'q."

        parts: list[str] = []
        if tasks:
            parts.append(f"Bugun {len(tasks)} ta ishingiz bor.")
            for task in tasks[:5]:
                when = format_when(task.remind_at)
                parts.append(f"{when} — {task.title}.")
            if len(tasks) > 5:
                parts.append(f"Yana {len(tasks) - 5} ta ish bor.")
        else:
            parts.append("Bugunga belgilangan vaqtli ish yo'q.")

        if projects:
            names = ", ".join(p.name for p in projects[:3])
            parts.append(f"Faol loyihalar: {names}.")

        return " ".join(parts)
