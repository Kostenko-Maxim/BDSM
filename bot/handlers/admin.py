from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.repositories import AdminRepo
from bot.keyboards.inline import BACK_TO_MENU, admin_detail_kb, admin_list_kb
from bot.middlewares.auth import invalidate_admin_cache

router = Router()


class AdminFSM(StatesGroup):
    waiting_new_admin_id = State()


@router.callback_query(F.data == "admin:list")
async def cb_admin_list(
    callback: CallbackQuery, session: AsyncSession, is_admin: bool, is_superadmin: bool
) -> None:
    if not is_admin:
        await callback.message.edit_text("⛔ Нет доступа")
        return
    repo = AdminRepo(session)
    admins = await repo.get_all()
    kb = admin_list_kb(admins, settings.superadmin_id, is_superadmin)
    await callback.message.edit_text("👥 Список администраторов:", reply_markup=kb)


@router.callback_query(F.data.startswith("admin:info:"))
async def cb_admin_info(
    callback: CallbackQuery, session: AsyncSession, is_admin: bool, is_superadmin: bool
) -> None:
    if not is_admin:
        await callback.message.edit_text("⛔ Нет доступа")
        return
    tg_id = int(callback.data.split(":")[2])
    repo = AdminRepo(session)
    admin = await repo.get_by_telegram_id(tg_id)
    if admin is None:
        await callback.message.edit_text("❌ Админ не найден")
        return
    role_text = "Суперадмин" if admin.role == "superadmin" else "Админ"
    text = (
        f"👤 <b>{admin.username or 'Без username'}</b>\n"
        f"ID: <code>{admin.telegram_id}</code>\n"
        f"Роль: {role_text}\n"
        f"Добавлен: {admin.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    can_delete = is_superadmin and admin.telegram_id != settings.superadmin_id
    kb = admin_detail_kb(admin.telegram_id, can_delete)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "admin:add")
async def cb_admin_add(
    callback: CallbackQuery, is_superadmin: bool, state: FSMContext
) -> None:
    if not is_superadmin:
        await callback.message.edit_text("⛔ Только суперадмин может добавлять админов")
        return
    await callback.message.edit_text(
        "Введите Telegram ID нового админа (числом):",
        reply_markup=BACK_TO_MENU,
    )
    await state.set_state(AdminFSM.waiting_new_admin_id)


@router.message(AdminFSM.waiting_new_admin_id)
async def process_new_admin_id(
    message: Message, session: AsyncSession, is_superadmin: bool, state: FSMContext, bot: Bot
) -> None:
    if not is_superadmin:
        await message.answer("⛔ Нет доступа")
        await state.clear()
        return
    text = message.text.strip() if message.text else ""
    if not text.isdigit():
        await message.answer("❌ Введите корректный числовой Telegram ID:")
        return

    tg_id = int(text)
    repo = AdminRepo(session)
    existing = await repo.get_by_telegram_id(tg_id)
    if existing:
        await message.answer("ℹ️ Этот пользователь уже является админом.", reply_markup=BACK_TO_MENU)
        await state.clear()
        return

    username: str | None = None
    try:
        chat = await bot.get_chat(tg_id)
        username = chat.username
    except Exception:
        pass

    await repo.create(tg_id, username=username, role="admin")
    invalidate_admin_cache(tg_id)
    display = f"@{username}" if username else f"ID <code>{tg_id}</code>"
    await message.answer(
        f"✅ Админ {display} успешно добавлен.",
        parse_mode="HTML",
        reply_markup=BACK_TO_MENU,
    )
    await state.clear()


@router.callback_query(F.data.startswith("admin:delete:"))
async def cb_admin_delete(
    callback: CallbackQuery, session: AsyncSession, is_superadmin: bool
) -> None:
    if not is_superadmin:
        await callback.message.edit_text("⛔ Только суперадмин может удалять админов")
        return
    tg_id = int(callback.data.split(":")[2])
    if tg_id == settings.superadmin_id:
        await callback.message.edit_text("❌ Нельзя удалить суперадмина")
        return
    repo = AdminRepo(session)
    deleted = await repo.delete_by_telegram_id(tg_id)
    if not deleted:
        await callback.message.edit_text("❌ Админ не найден")
        return
    invalidate_admin_cache(tg_id)
    admins = await repo.get_all()
    kb = admin_list_kb(admins, settings.superadmin_id, is_superadmin)
    await callback.message.edit_text("👥 Список администраторов:", reply_markup=kb)
