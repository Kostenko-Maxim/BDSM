"""Утилиты."""

from datetime import datetime

import pytz

from bot.config import settings


def format_datetime_local(dt: datetime) -> str:
    """Форматирует datetime в локальном часовом поясе (из settings.timezone)."""
    tz = pytz.timezone(settings.timezone)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M")
