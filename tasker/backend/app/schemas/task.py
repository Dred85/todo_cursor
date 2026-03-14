from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    timezone: str | None = None
    source: str = Field(default="webapp")


class TaskResponse(BaseModel):
    task_id: int
    title: str
    due_at: str | None  # ISO format string
    status: str


class UpdateTaskRequest(BaseModel):
    title: str | None = None
    due_at: str | None = None  # ISO format string
    status: str | None = None


class ErrorResponse(BaseModel):
    ok: bool = False
    message: str

