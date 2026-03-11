import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.engine import async_session
from bot.db.repositories import AdminRepo

# Кэш прав: user_id -> (is_admin, is_superadmin, timestamp)
_ADMIN_CACHE: dict[int, tuple[bool, bool, float]] = {}
_CACHE_TTL = 300.0  # 5 мин — меньше обращений к БД

# Callback'и без обращения к БД (навигация, FSM, меню)
_CALLBACKS_NO_SESSION = frozenset({
    "cal:ignore", "cal:cancel", "menu:main", "admin:add", "channels:add",
    "broadcast:start", "bcast:schedule", "bcast:cancel",
})
_CALLBACKS_NO_SESSION_PREFIXES = (
    "cal:prev:", "cal:next:", "cal:day:", "cal:hour:",
    "cal:back_to_cal:", "cal:back_to_hour:",
)


def _callback_needs_session(data: str | None) -> bool:
    if not data:
        return True
    if data in _CALLBACKS_NO_SESSION:
        return False
    return not data.startswith(_CALLBACKS_NO_SESSION_PREFIXES)


def invalidate_admin_cache(user_id: int) -> None:
    """Сбросить кэш прав при удалении/добавлении админа."""
    _ADMIN_CACHE.pop(user_id, None)


async def _resolve_admin(
    user_id: int, username: str | None, session: AsyncSession
) -> tuple[bool, bool]:
    repo = AdminRepo(session)
    if user_id == settings.superadmin_id:
        is_superadmin = is_admin = True
        existing = await repo.get_by_telegram_id(user_id)
        if existing is None:
            await repo.create(user_id, username, role="superadmin")
        elif existing.username != username:
            await repo.update_username(user_id, username)
    else:
        existing = await repo.get_by_telegram_id(user_id)
        is_admin = existing is not None
        is_superadmin = False
        if existing and existing.username != username:
            await repo.update_username(user_id, username)
    return is_admin, is_superadmin


class AdminMiddleware(BaseMiddleware):
    """Injects db session and admin status; skips session for callbacks that don't need it."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        username: str | None = None
        callback_data: str | None = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            username = event.from_user.username
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
            username = event.from_user.username
            callback_data = event.data

        is_admin = False
        is_superadmin = False
        needs_session = not isinstance(event, CallbackQuery) or _callback_needs_session(
            callback_data
        )

        if user_id is not None:
            now = time.monotonic()
            cached = _ADMIN_CACHE.get(user_id)
            if cached is not None and (now - cached[2]) < _CACHE_TTL:
                is_admin, is_superadmin = cached[0], cached[1]
                if not needs_session:
                    data["session"] = None
                    data["is_admin"] = is_admin
                    data["is_superadmin"] = is_superadmin
                    return await handler(event, data)
            elif not needs_session:
                async with async_session() as session:
                    is_admin, is_superadmin = await _resolve_admin(user_id, username, session)
                _ADMIN_CACHE[user_id] = (is_admin, is_superadmin, now)
                data["session"] = None
                data["is_admin"] = is_admin
                data["is_superadmin"] = is_superadmin
                return await handler(event, data)

        async with async_session() as session:
            if user_id is not None:
                now = time.monotonic()
                cached = _ADMIN_CACHE.get(user_id)
                if cached is not None and (now - cached[2]) < _CACHE_TTL:
                    is_admin, is_superadmin = cached[0], cached[1]
                else:
                    is_admin, is_superadmin = await _resolve_admin(user_id, username, session)
                    _ADMIN_CACHE[user_id] = (is_admin, is_superadmin, now)

            data["session"] = session
            data["is_admin"] = is_admin
            data["is_superadmin"] = is_superadmin
            return await handler(event, data)
