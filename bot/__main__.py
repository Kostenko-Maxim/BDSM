import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.db.engine import engine
from bot.db.models import Base
from bot.handlers import get_all_routers
from bot.loader import bot
from bot.middlewares.auth import AdminMiddleware
from bot.services.scheduler import restore_pending_jobs, scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")

    await restore_pending_jobs()
    scheduler.start()
    logger.info("Scheduler started")

    me = await bot.get_me()
    logger.info("Bot started: @%s", me.username)


async def on_shutdown() -> None:
    scheduler.shutdown(wait=False)
    await engine.dispose()
    logger.info("Bot stopped")


async def main() -> None:
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(AdminMiddleware())
    dp.callback_query.middleware(AdminMiddleware())

    for router in get_all_routers():
        dp.include_router(router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
