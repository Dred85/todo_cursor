from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ParsedTask:
    title: str
    due_at: datetime | None
    parsing_errors: list[str] = field(default_factory=list)

