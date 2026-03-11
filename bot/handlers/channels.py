import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories import AdminRepo, ChannelRepo
from bot.keyboards.inline import (
    MAIN_MENU,
    REMOVE_REPLY_KB,
    channel_detail_kb,
    channel_list_kb,
    channel_request_kb,
)

logger = logging.getLogger(__name__)

router = Router()


class ChannelFSM(StatesGroup):
    adding_channels = State()


@router.callback_query(F.data == "channels:list")
async def cb_channel_list(
    callback: CallbackQuery, session: AsyncSession, is_admin: bool
) -> None:
    if not is_admin:
        await callback.message.edit_text("⛔ Нет доступа")
        return
    repo = ChannelRepo(session)
    channels = await repo.get_all()
    if not channels:
        text = "📢 Каналы не подключены.\n\nНажмите кнопку ниже, чтобы добавить канал."
    else:
        text = "📢 Подключённые каналы:"
    kb = channel_list_kb(channels)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "channels:add")
async def cb_channel_add(
    callback: CallbackQuery, is_admin: bool, state: FSMContext
) -> None:
    if not is_admin:
        await callback.message.edit_text("⛔ Нет доступа")
        return
    await state.set_state(ChannelFSM.adding_channels)
    await callback.message.answer(
        "📢 Нажмите кнопку ниже, чтобы выбрать канал.\n"
        "Можно добавлять по одному — после каждого выбора кнопка останется.\n\n"
        "Когда закончите, нажмите «✅ Готово».",
        reply_markup=channel_request_kb(),
    )


@router.message(ChannelFSM.adding_channels, F.chat_shared)
async def process_chat_shared(
    message: Message,
    session: AsyncSession,
    is_admin: bool,
    bot: Bot,
) -> None:
    if not is_admin:
        return

    chat_id = message.chat_shared.chat_id

    try:
        chat = await bot.get_chat(chat_id)
        title = chat.title or str(chat_id)
    except Exception:
        await message.answer(
            "❌ Не удалось получить информацию о канале.",
            reply_markup=channel_request_kb(),
        )
        return

    try:
        member = await bot.get_chat_member(chat_id, bot.id)
        if member.status not in ("administrator", "creator"):
            await message.answer(
                f"❌ Бот не является администратором канала «{title}».\n"
                "Добавьте бота как админа и попробуйте снова.",
                reply_markup=channel_request_kb(),
            )
            return
    except Exception:
        await message.answer(
            "❌ Не удалось проверить права бота в канале.",
            reply_markup=channel_request_kb(),
        )
        return

    channel_repo = ChannelRepo(session)
    existing = await channel_repo.get_by_chat_id(chat_id)
    if existing:
        await message.answer(
            f"ℹ️ Канал «{existing.title}» уже подключён.\n\n"
            "Выберите другой канал или нажмите «✅ Готово».",
            reply_markup=channel_request_kb(),
        )
        return

    admin_repo = AdminRepo(session)
    admin = await admin_repo.get_by_telegram_id(message.from_user.id)
    await channel_repo.create(chat_id, title, admin.id)

    await message.answer(
        f"✅ Канал «{title}» успешно подключён!\n\n"
        "Можете выбрать ещё канал или нажмите «✅ Готово».",
        reply_markup=channel_request_kb(),
    )


@router.message(ChannelFSM.adding_channels, F.text == "✅ Готово")
async def process_done_adding(
    message: Message, state: FSMContext
) -> None:
    await state.clear()
    await message.answer("👌", reply_markup=REMOVE_REPLY_KB)
    await message.answer(
        "📋 Главное меню\n\nВыберите действие:",
        reply_markup=MAIN_MENU,
    )


@router.callback_query(F.data.startswith("channels:detail:"))
async def cb_channel_detail(
    callback: CallbackQuery, session: AsyncSession, is_admin: bool
) -> None:
    if not is_admin:
        await callback.message.edit_text("⛔ Нет доступа")
        return
    channel_id = int(callback.data.split(":")[2])
    repo = ChannelRepo(session)
    channel = await repo.get_by_id(channel_id)
    if channel is None:
        await callback.message.edit_text("❌ Канал не найден")
        return
    status = "Активен ✅" if channel.is_active else "Отключён ❌"
    text = (
        f"📢 <b>{channel.title}</b>\n"
        f"Chat ID: <code>{channel.telegram_chat_id}</code>\n"
        f"Статус: {status}\n"
        f"Добавлен: {channel.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    kb = channel_detail_kb(channel)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("channels:toggle:"))
async def cb_channel_toggle(
    callback: CallbackQuery, session: AsyncSession, is_admin: bool
) -> None:
    if not is_admin:
        await callback.message.edit_text("⛔ Нет доступа")
        return
    channel_id = int(callback.data.split(":")[2])
    repo = ChannelRepo(session)
    channel = await repo.toggle_active(channel_id)
    if channel is None:
        await callback.message.edit_text("❌ Канал не найден")
        return
    status = "Активен ✅" if channel.is_active else "Отключён ❌"
    text = (
        f"📢 <b>{channel.title}</b>\n"
        f"Chat ID: <code>{channel.telegram_chat_id}</code>\n"
        f"Статус: {status}\n"
        f"Добавлен: {channel.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    kb = channel_detail_kb(channel)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("channels:delete:"))
async def cb_channel_delete(
    callback: CallbackQuery, session: AsyncSession, is_admin: bool
) -> None:
    if not is_admin:
        await callback.message.edit_text("⛔ Нет доступа")
        return
    channel_id = int(callback.data.split(":")[2])
    repo = ChannelRepo(session)
    deleted = await repo.delete_by_id(channel_id)
    if not deleted:
        await callback.message.edit_text("❌ Канал не найден")
        return
    channels = await repo.get_all()
    kb = channel_list_kb(channels)
    text = "📢 Подключённые каналы:" if channels else "📢 Каналы не подключены."
    await callback.message.edit_text(text, reply_markup=kb)
