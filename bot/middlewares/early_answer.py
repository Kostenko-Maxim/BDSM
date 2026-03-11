"""Middleware для мгновенного ответа на callback — убирает загрузку до фильтров и БД."""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject, Update


class EarlyAnswerMiddleware(BaseMiddleware):
    """Вызывает callback.answer() в outer scope — до фильтров, FSM и любых операций."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        cq: CallbackQuery | None = None
        if isinstance(event, CallbackQuery):
            cq = event
        elif isinstance(event, Update) and event.callback_query:
            cq = event.callback_query
        if cq:
            await cq.answer()
        return await handler(event, data)
