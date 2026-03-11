from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import MAIN_MENU

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, is_admin: bool) -> None:
    if not is_admin:
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return
    await message.answer(
        "👋 Добро пожаловать в BDSM-бот!\n\n"
        "Broadcast Distribution & Scheduling Manager\n\n"
        "Выберите действие:",
        reply_markup=MAIN_MENU,
    )


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, is_admin: bool) -> None:
    if not is_admin:
        await callback.message.edit_text("⛔ Нет доступа")
        return
    await callback.message.edit_text(
        "📋 Главное меню\n\nВыберите действие:",
        reply_markup=MAIN_MENU,
    )
