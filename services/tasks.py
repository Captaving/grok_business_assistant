import sqlite3
import time
from dataclasses import dataclass
from datetime import date

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    details       TEXT    NOT NULL DEFAULT '',
    quote         TEXT    NOT NULL DEFAULT '',
    deadline      TEXT    NOT NULL DEFAULT '',  -- как сказал руководитель, для чтения
    deadline_date TEXT,                          -- ГГГГ-ММ-ДД, для сортировки и утренней сводки
    urgent        INTEGER NOT NULL DEFAULT 0,
    source        TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL DEFAULT 'proposed',  -- proposed | open | done | rejected
    created_at    INTEGER NOT NULL,
    closed_at     INTEGER,
    remind_at     INTEGER
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


@dataclass
class TaskDraft:
    title: str
    details: str = ""
    quote: str = ""
    deadline: str = ""
    deadline_date: date | None = None
    urgent: bool = False


@dataclass
class Task:
    id: int
    title: str
    details: str
    quote: str
    deadline: str
    deadline_date: date | None
    urgent: bool
    source: str
    status: str
    created_at: int
    closed_at: int | None
    remind_at: int | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Task":
        data = dict(row)
        data["deadline_date"] = date.fromisoformat(data["deadline_date"]) if data["deadline_date"] else None
        data["urgent"] = bool(data["urgent"])
        return cls(**data)


class TaskStore:
    """Задачи в SQLite. Запросы крошечные, поэтому синхронный sqlite3 цикл событий не тормозит."""

    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def add(self, draft: TaskDraft, source: str, status: str = "proposed") -> Task:
        cur = self.db.execute(
            "INSERT INTO tasks (title, details, quote, deadline, deadline_date, urgent, source, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                draft.title, draft.details, draft.quote, draft.deadline,
                draft.deadline_date.isoformat() if draft.deadline_date else None,
                int(draft.urgent), source, status, int(time.time()),
            ),
        )
        self.db.commit()
        return self.get(cur.lastrowid)

    def get(self, task_id: int) -> Task | None:
        row = self.db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return Task.from_row(row) if row else None

    def set_status(self, task_id: int, status: str) -> Task | None:
        if status in ("done", "rejected"):
            self.db.execute(
                "UPDATE tasks SET status = ?, closed_at = ?, remind_at = NULL WHERE id = ?",
                (status, int(time.time()), task_id),
            )
        else:
            self.db.execute("UPDATE tasks SET status = ?, closed_at = NULL WHERE id = ?", (status, task_id))
        self.db.commit()
        return self.get(task_id)

    def set_reminder(self, task_id: int, remind_at: int | None) -> Task | None:
        self.db.execute("UPDATE tasks SET remind_at = ? WHERE id = ?", (remind_at, task_id))
        self.db.commit()
        return self.get(task_id)

    def list_open(self, offset: int = 0, limit: int = 1000) -> tuple[list[Task], int]:
        total = self.db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'open'").fetchone()[0]
        rows = self.db.execute(
            "SELECT * FROM tasks WHERE status = 'open'"
            " ORDER BY urgent DESC, deadline_date IS NULL, deadline_date, id LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [Task.from_row(r) for r in rows], total

    def list_closed(self, limit: int = 10) -> list[Task]:
        rows = self.db.execute(
            "SELECT * FROM tasks WHERE status = 'done' ORDER BY closed_at DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Task.from_row(r) for r in rows]

    def due_reminders(self, now: int) -> list[Task]:
        rows = self.db.execute(
            "SELECT * FROM tasks WHERE status = 'open' AND remind_at IS NOT NULL AND remind_at <= ? ORDER BY remind_at",
            (now,),
        ).fetchall()
        return [Task.from_row(r) for r in rows]

    def get_meta(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
        self.db.commit()
