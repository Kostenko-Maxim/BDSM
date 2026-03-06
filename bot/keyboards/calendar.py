import calendar
from datetime import date, datetime

import pytz
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings

MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

_IGNORE = "cal:ignore"
_CANCEL = "cal:cancel"


def _today() -> date:
    tz = pytz.timezone(settings.timezone)
    return datetime.now(tz).date()


def calendar_kb(year: int, month: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    today = _today()

    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    builder.row(
        InlineKeyboardButton(text="◀", callback_data=f"cal:prev:{prev_year}-{prev_month:02d}"),
        InlineKeyboardButton(text=f"{MONTHS_RU[month]} {year}", callback_data=_IGNORE),
        InlineKeyboardButton(text="▶", callback_data=f"cal:next:{next_year}-{next_month:02d}"),
    )

    builder.row(*[InlineKeyboardButton(text=d, callback_data=_IGNORE) for d in DAYS_RU])

    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data=_IGNORE))
            else:
                d = date(year, month, day_num)
                if d < today:
                    row.append(InlineKeyboardButton(text="·", callback_data=_IGNORE))
                else:
                    row.append(
                        InlineKeyboardButton(
                            text=str(day_num),
                            callback_data=f"cal:day:{d.isoformat()}",
                        )
                    )
        builder.row(*row)

    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=_CANCEL))
    return builder.as_markup()


def hour_kb(date_str: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"📅 {date_str}  —  выберите час:", callback_data=_IGNORE)
    )

    today = _today()
    tz = pytz.timezone(settings.timezone)
    now = datetime.now(tz)
    selected_date = date.fromisoformat(date_str)

    hours = list(range(24))
    for i in range(0, 24, 4):
        row = []
        for h in hours[i : i + 4]:
            if selected_date == today and h < now.hour:
                row.append(InlineKeyboardButton(text="·", callback_data=_IGNORE))
            else:
                row.append(
                    InlineKeyboardButton(
                        text=f"{h:02d}",
                        callback_data=f"cal:hour:{date_str}:{h:02d}",
                    )
                )
        builder.row(*row)

    builder.row(
        InlineKeyboardButton(text="🔙 К календарю", callback_data=f"cal:back_to_cal:{date_str}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=_CANCEL),
    )
    return builder.as_markup()


def minute_kb(date_str: str, hour: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"📅 {date_str}  {hour:02d}:??  —  выберите минуты:",
            callback_data=_IGNORE,
        )
    )

    today = _today()
    tz = pytz.timezone(settings.timezone)
    now = datetime.now(tz)
    selected_date = date.fromisoformat(date_str)

    minutes = list(range(0, 60, 5))
    for i in range(0, len(minutes), 4):
        row = []
        for m in minutes[i : i + 4]:
            if selected_date == today and hour == now.hour and m <= now.minute:
                row.append(InlineKeyboardButton(text="·", callback_data=_IGNORE))
            else:
                row.append(
                    InlineKeyboardButton(
                        text=f"{m:02d}",
                        callback_data=f"cal:min:{date_str}:{hour:02d}:{m:02d}",
                    )
                )
        builder.row(*row)

    builder.row(
        InlineKeyboardButton(text="🔙 К часам", callback_data=f"cal:back_to_hour:{date_str}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=_CANCEL),
    )
    return builder.as_markup()
