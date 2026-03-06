from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import settings
from bot.db.engine import async_session
from bot.db.repositories import AdminRepo


class AdminMiddleware(BaseMiddleware):
    """Injects db session and admin repo; marks user as admin/superadmin."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            repo = AdminRepo(session)

            user_id: int | None = None
            if isinstance(event, Message) and event.from_user:
                user_id = event.from_user.id
            elif isinstance(event, CallbackQuery) and event.from_user:
                user_id = event.from_user.id

            is_admin = False
            is_superadmin = False
            username: str | None = None

            if isinstance(event, Message) and event.from_user:
                username = event.from_user.username
            elif isinstance(event, CallbackQuery) and event.from_user:
                username = event.from_user.username

            if user_id is not None:
                if user_id == settings.superadmin_id:
                    is_superadmin = True
                    is_admin = True
                    existing = await repo.get_by_telegram_id(user_id)
                    if existing is None:
                        await repo.create(user_id, username, role="superadmin")
                    elif existing.username != username:
                        await repo.update_username(user_id, username)
                else:
                    existing = await repo.get_by_telegram_id(user_id)
                    if existing is not None:
                        is_admin = True
                        if existing.username != username:
                            await repo.update_username(user_id, username)

            data["session"] = session
            data["is_admin"] = is_admin
            data["is_superadmin"] = is_superadmin

            return await handler(event, data)
