from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def init_sqlite(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              title TEXT NOT NULL,
              due_at_utc TEXT NULL,
              status TEXT NOT NULL,
              source TEXT NOT NULL,
              created_at_utc TEXT NOT NULL,
              updated_at_utc TEXT NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);")


@dataclass(frozen=True)
class TaskRecord:
    id: int
    user_id: int
    title: str
    due_at: datetime | None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime


class SqliteTaskRepository:
    def __init__(self, db_path: str | Path):
        self._path = Path(db_path)

    def create_task(
        self,
        *,
        user_id: int,
        title: str,
        due_at: datetime | None,
        status: str,
        source: str,
        now_utc: datetime,
    ) -> TaskRecord:
        created_at = now_utc
        updated_at = now_utc
        due_at_utc = due_at.astimezone(timezone.utc).isoformat() if due_at else None
        with sqlite3.connect(self._path) as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks(
                  user_id, title, due_at_utc, status, source,
                  created_at_utc, updated_at_utc
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    user_id,
                    title,
                    due_at_utc,
                    status,
                    source,
                    created_at.isoformat(),
                    updated_at.isoformat(),
                ),
            )
            task_id = int(cur.lastrowid)
        return TaskRecord(
            id=task_id,
            user_id=user_id,
            title=title,
            due_at=due_at,
            status=status,
            source=source,
            created_at=created_at,
            updated_at=updated_at,
        )

    def get_task(self, *, task_id: int, user_id: int) -> TaskRecord | None:
        with sqlite3.connect(self._path) as conn:
            row = conn.execute(
                """
                SELECT id, user_id, title, due_at_utc, status, source, created_at_utc, updated_at_utc
                FROM tasks
                WHERE id=? AND user_id=?
                """,
                (task_id, user_id),
            ).fetchone()
        if not row:
            return None
        task_id_db, uid, title, due_at_utc, status, source, created_at_utc, updated_at_utc = row
        due_at = datetime.fromisoformat(due_at_utc).replace(tzinfo=timezone.utc) if due_at_utc else None
        created_at = datetime.fromisoformat(created_at_utc).replace(tzinfo=timezone.utc)
        updated_at = datetime.fromisoformat(updated_at_utc).replace(tzinfo=timezone.utc)
        return TaskRecord(
            id=int(task_id_db),
            user_id=int(uid),
            title=str(title),
            due_at=due_at,
            status=str(status),
            source=str(source),
            created_at=created_at,
            updated_at=updated_at,
        )

    def update_task(
        self,
        *,
        task_id: int,
        user_id: int,
        title: str | None = None,
        due_at: datetime | None = None,
        status: str | None = None,
        now_utc: datetime,
    ) -> TaskRecord | None:
        task = self.get_task(task_id=task_id, user_id=user_id)
        if not task:
            return None

        new_title = title if title is not None else task.title
        new_due_at = due_at if due_at is not None else task.due_at
        new_status = status if status is not None else task.status

        due_at_utc = new_due_at.astimezone(timezone.utc).isoformat() if new_due_at else None

        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                UPDATE tasks
                SET title=?, due_at_utc=?, status=?, updated_at_utc=?
                WHERE id=? AND user_id=?
                """,
                (new_title, due_at_utc, new_status, now_utc.isoformat(), task_id, user_id),
            )

        return TaskRecord(
            id=task.id,
            user_id=task.user_id,
            title=new_title,
            due_at=new_due_at,
            status=new_status,
            source=task.source,
            created_at=task.created_at,
            updated_at=now_utc,
        )

    def delete_task(self, *, task_id: int, user_id: int) -> bool:
        with sqlite3.connect(self._path) as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, user_id))
            return cur.rowcount > 0

    def list_tasks(self, *, user_id: int, limit: int = 50) -> list[TaskRecord]:
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, title, due_at_utc, status, source, created_at_utc, updated_at_utc
                FROM tasks
                WHERE user_id=? ORDER BY id DESC LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        out: list[TaskRecord] = []
        for task_id, uid, title, due_at_utc, status, source, created_at_utc, updated_at_utc in rows:
            due_at = datetime.fromisoformat(due_at_utc).replace(tzinfo=timezone.utc) if due_at_utc else None
            created_at = datetime.fromisoformat(created_at_utc).replace(tzinfo=timezone.utc)
            updated_at = datetime.fromisoformat(updated_at_utc).replace(tzinfo=timezone.utc)
            out.append(
                TaskRecord(
                    id=int(task_id),
                    user_id=int(uid),
                    title=str(title),
                    due_at=due_at,
                    status=str(status),
                    source=str(source),
                    created_at=created_at,
                    updated_at=updated_at,
                )
            )
        return out

