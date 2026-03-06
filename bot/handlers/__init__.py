from aiogram import Router

from bot.handlers.start import router as start_router
from bot.handlers.admin import router as admin_router
from bot.handlers.channels import router as channels_router
from bot.handlers.broadcast import router as broadcast_router
from bot.handlers.schedule import router as schedule_router


def get_all_routers() -> list[Router]:
    return [
        start_router,
        admin_router,
        channels_router,
        schedule_router,
        broadcast_router,
    ]
