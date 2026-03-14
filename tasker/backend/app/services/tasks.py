from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol

from app.services.errors import TaskPermissionError, TaskValidationError
from app.storage.sqlite import SqliteTaskRepository, TaskRecord


class TaskSource(str, Enum):
    telegram_chat = "telegram_chat"
    webapp = "webapp"


class ReminderScheduler(Protocol):
    def schedule_reminder(self, task: TaskRecord) -> None:  # pragma: no cover
        ...


class NullReminderScheduler:
    def schedule_reminder(self, task: TaskRecord) -> None:  # pragma: no cover
        return None


@dataclass(frozen=True)
class CreateTaskResult:
    task: TaskRecord


class TaskService:
    def __init__(self, repo: SqliteTaskRepository, scheduler: ReminderScheduler | None = None):
        self._repo = repo
        self._scheduler = scheduler or NullReminderScheduler()

    def create_task(
        self,
        *,
        user_id: int,
        title: str,
        due_at: datetime | None,
        source: TaskSource,
        now: datetime | None = None,
    ) -> CreateTaskResult:
        if user_id <= 0:
            raise TaskPermissionError("Unknown user")

        title_n = (title or "").strip()
        if not title_n:
            raise TaskValidationError("Empty title")
        if len(title_n) < 2:
            raise TaskValidationError("Title too short")
        if len(title_n) > 255:
            raise TaskValidationError("Title too long")

        now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if due_at is not None:
            if due_at.tzinfo is None or due_at.tzinfo.utcoffset(due_at) is None:
                raise TaskValidationError("Due date must be timezone-aware")
            due_utc = due_at.astimezone(timezone.utc)
            if due_utc < now_utc - timedelta(minutes=1):
                raise TaskValidationError("Due date in the past")

        task = self._repo.create_task(
            user_id=user_id,
            title=title_n,
            due_at=due_at,
            status="todo",
            source=source.value,
            now_utc=now_utc,
        )

        if task.due_at is not None:
            try:
                self._scheduler.schedule_reminder(task)
            except Exception:
                # По контракту: задача создаётся даже если планирование напоминания упало.
                pass

        return CreateTaskResult(task=task)

    def update_task(
        self,
        *,
        task_id: int,
        user_id: int,
        title: str | None = None,
        due_at: datetime | None = None,
        status: str | None = None,
        now: datetime | None = None,
    ) -> TaskRecord:
        task = self._repo.get_task(task_id=task_id, user_id=user_id)
        if not task:
            raise TaskPermissionError("Task not found")

        now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

        if title is not None:
            title_n = (title or "").strip()
            if not title_n:
                raise TaskValidationError("Empty title")
            if len(title_n) < 2:
                raise TaskValidationError("Title too short")
            if len(title_n) > 255:
                raise TaskValidationError("Title too long")
        else:
            title_n = None

        if due_at is not None:
            if due_at.tzinfo is None or due_at.tzinfo.utcoffset(due_at) is None:
                raise TaskValidationError("Due date must be timezone-aware")
            due_utc = due_at.astimezone(timezone.utc)
            if due_utc < now_utc - timedelta(minutes=1):
                raise TaskValidationError("Due date in the past")

        updated = self._repo.update_task(
            task_id=task_id,
            user_id=user_id,
            title=title_n,
            due_at=due_at,
            status=status,
            now_utc=now_utc,
        )

        if not updated:
            raise TaskPermissionError("Task not found")

        return updated

    def delete_task(self, *, task_id: int, user_id: int) -> None:
        if user_id <= 0:
            raise TaskPermissionError("Unknown user")

        deleted = self._repo.delete_task(task_id=task_id, user_id=user_id)
        if not deleted:
            raise TaskPermissionError("Task not found")

