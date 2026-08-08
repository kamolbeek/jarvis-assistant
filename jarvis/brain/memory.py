"""Barqaror xotira — Jarvis'ni har safar noldan boshlamaslik uchun.

Ikki xil narsa saqlanadi:
  * faktlar — "Kamoliddin ertalab soat 8 da hisobot oladi" kabi barqaror bilim;
  * suhbatlar — nima so'ralgani va nima qilingani (keyin qidirish uchun).

SQLite tanlangan: bitta fayl, server kerak emas, Jarvis ishlamayotganda ham
`sqlite3` bilan ochib ko'rish mumkin.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("jarvis.brain.memory")

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'umumiy',
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    text        TEXT NOT NULL,
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, id);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
"""


@dataclass
class Fact:
    key: str
    value: str
    category: str
    updated_at: float


class Memory:
    """Jarvis xotirasi. Barcha metodlar sinxron — SQLite tez, bloklanish sezilmaydi."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        log.info("Xotira ochildi: %s", path)

    def close(self) -> None:
        self._conn.close()

    # --- Faktlar ---

    def remember(self, key: str, value: str, category: str = "umumiy") -> None:
        """Faktni saqlaydi yoki yangilaydi."""
        self._conn.execute(
            "INSERT INTO facts(key, value, category, updated_at) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "category=excluded.category, updated_at=excluded.updated_at",
            (key, value, category, time.time()),
        )
        self._conn.commit()

    def forget(self, key: str) -> bool:
        cursor = self._conn.execute("DELETE FROM facts WHERE key = ?", (key,))
        self._conn.commit()
        return cursor.rowcount > 0

    def recall(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM facts WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def search(self, query: str, limit: int = 20) -> list[Fact]:
        """Kalit va qiymat bo'yicha oddiy qidiruv."""
        pattern = f"%{query}%"
        rows = self._conn.execute(
            "SELECT * FROM facts WHERE key LIKE ? OR value LIKE ? "
            "ORDER BY updated_at DESC LIMIT ?",
            (pattern, pattern, limit),
        ).fetchall()
        return [Fact(r["key"], r["value"], r["category"], r["updated_at"]) for r in rows]

    def all_facts(self, limit: int = 200) -> list[Fact]:
        rows = self._conn.execute(
            "SELECT * FROM facts ORDER BY category, key LIMIT ?", (limit,)
        ).fetchall()
        return [Fact(r["key"], r["value"], r["category"], r["updated_at"]) for r in rows]

    # --- Suhbatlar ---

    def add_turn(self, session_id: str, role: str, text: str) -> None:
        self._conn.execute(
            "INSERT INTO turns(session_id, role, text, created_at) VALUES(?, ?, ?, ?)",
            (session_id, role, text, time.time()),
        )
        self._conn.commit()

    def recent_turns(self, limit: int = 20) -> list[dict[str, str]]:
        rows = self._conn.execute(
            "SELECT role, text FROM turns ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"role": r["role"], "text": r["text"]} for r in reversed(rows)]

    def search_turns(self, query: str, limit: int = 20) -> list[dict[str, str]]:
        rows = self._conn.execute(
            "SELECT role, text, created_at FROM turns WHERE text LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [
            {
                "role": r["role"],
                "text": r["text"],
                "vaqt": time.strftime("%Y-%m-%d %H:%M", time.localtime(r["created_at"])),
            }
            for r in rows
        ]

    # --- Tizim ko'rsatmasi uchun ---

    def context_block(self, max_facts: int = 60) -> str:
        """Faktlarni tizim ko'rsatmasiga qo'shish uchun matn ko'rinishida qaytaradi."""
        facts = self.all_facts(limit=max_facts)
        if not facts:
            return ""

        by_category: dict[str, list[Fact]] = {}
        for fact in facts:
            by_category.setdefault(fact.category, []).append(fact)

        lines: list[str] = []
        for category, items in sorted(by_category.items()):
            lines.append(f"[{category}]")
            lines.extend(f"  {item.key}: {item.value}" for item in items)
        return "\n".join(lines)

    def stats(self) -> dict[str, int]:
        facts = self._conn.execute("SELECT COUNT(*) AS n FROM facts").fetchone()["n"]
        turns = self._conn.execute("SELECT COUNT(*) AS n FROM turns").fetchone()["n"]
        return {"faktlar": facts, "suhbat_qatorlari": turns}

    def export_json(self) -> str:
        """Xotirani JSON sifatida chiqaradi — zaxira nusxa yoki ko'chirish uchun."""
        return json.dumps(
            {
                "faktlar": [
                    {"key": f.key, "value": f.value, "category": f.category}
                    for f in self.all_facts(limit=10_000)
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
