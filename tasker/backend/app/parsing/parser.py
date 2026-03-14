from __future__ import annotations

import re
from datetime import datetime, timezone as dt_timezone

from dateparser.search import search_dates
from dateutil import tz

from .models import ParsedTask


_WS_RE = re.compile(r"\s+")


def _normalize_ws(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _get_tzinfo(tz_name: str | None):
    if not tz_name:
        return dt_timezone.utc
    tzinfo = tz.gettz(tz_name)
    return tzinfo or dt_timezone.utc


def _get_tz_name_for_dateparser(tz_name: str | None) -> str:
    """Преобразует имя часового пояса в формат, понятный dateparser."""
    if not tz_name:
        return "UTC"
    # dateparser понимает стандартные имена часовых поясов
    # Если это стандартное имя (Europe/Moscow, UTC и т.д.), возвращаем как есть
    return tz_name


def parse_task_text(
    raw_text: str,
    *,
    timezone: str | None = None,
    now: datetime | None = None,
    default_due_hour: int = 9,
) -> ParsedTask:
    """
    Контракт: текст после /task -> ParsedTask(title, due_at, parsing_errors).
    - title не должен быть пустым в успешном сценарии
    - due_at опционален
    - timezone не угадываем: используем tz пользователя или UTC
    """
    text = _normalize_ws(raw_text or "")
    if not text:
        return ParsedTask(
            title="",
            due_at=None,
            parsing_errors=["Пустой ввод. Пример: /task Купить билеты завтра 18:00"],
        )

    tzinfo = _get_tzinfo(timezone)
    tz_name_for_parser = _get_tz_name_for_dateparser(timezone)
    
    if now:
        if now.tzinfo is None:
            now = now.replace(tzinfo=dt_timezone.utc)
        now_dt = now.astimezone(tzinfo)
    else:
        now_dt = datetime.now(tzinfo)

    settings = {
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": tz_name_for_parser,
        "TO_TIMEZONE": tz_name_for_parser,
        "RELATIVE_BASE": now_dt,
        "PREFER_DATES_FROM": "future",
    }

    results = search_dates(
        text,
        settings=settings,
        languages=["ru", "en"],
        add_detected_language=False,
    )

    if not results:
        lowered = text.lower()
        vague_markers = ("когда-нибудь", "как-нибудь", "потом")
        if any(m in lowered for m in vague_markers):
            return ParsedTask(
                title="",
                due_at=None,
                parsing_errors=[
                    "Я не смог понять дату. Попробуй указать её точнее.",
                    "Например: завтра в 18:00",
                ],
            )
        return ParsedTask(title=text, due_at=None, parsing_errors=[])

    unique_phrases: list[str] = []
    for phrase, _dt in results:
        phrase_n = _normalize_ws(phrase)
        if phrase_n and phrase_n not in unique_phrases:
            unique_phrases.append(phrase_n)

    if len(unique_phrases) > 1:
        return ParsedTask(
            title="",
            due_at=None,
            parsing_errors=[
                "Нашёл несколько дат/времени в сообщении. Уточните одну дату, например: "
                "/task Отправить отчёт в пятницу 09:00"
            ],
        )

    phrase, dt = results[0]
    if dt is None:
        return ParsedTask(
            title="",
            due_at=None,
            parsing_errors=[
                "Я не смог понять дату. Попробуй указать её точнее.",
                "Например: завтра в 18:00",
            ],
        )

    phrase_n = _normalize_ws(phrase)
    title = _normalize_ws(re.sub(re.escape(phrase_n), " ", text, count=1, flags=re.IGNORECASE))

    if not title:
        return ParsedTask(
            title="",
            due_at=None,
            parsing_errors=[
                "Похоже, ты не указал описание задачи.",
                "Пример: /task Купить билеты завтра 18:00",
            ],
        )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tzinfo)

    # Если время не было указано явно (все компоненты времени = 0 или только дата),
    # устанавливаем время по умолчанию (09:00)
    # Проверяем, содержит ли исходный текст явное указание времени
    time_pattern = re.compile(r'\d{1,2}:\d{2}', re.IGNORECASE)
    has_explicit_time = bool(time_pattern.search(text))
    
    if not has_explicit_time and dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        dt = dt.replace(hour=default_due_hour, minute=0, second=0)

    return ParsedTask(title=title, due_at=dt, parsing_errors=[])
