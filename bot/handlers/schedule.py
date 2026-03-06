import logging
from datetime import datetime

import pytz
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.repositories import AdminRepo, ChannelRepo, ScheduledPostRepo
from bot.keyboards.calendar import calendar_kb, hour_kb, minute_kb
from bot.keyboards.inline import MAIN_MENU, scheduled_detail_kb, scheduled_list_kb
from bot.services.scheduler import cancel_scheduled_job, schedule_post
from bot.states.broadcast import BroadcastFSM

logger = logging.getLogger(__name__)

router = Router()


# --------------- Calendar navigation ---------------

@router.callback_query(BroadcastFSM.picking_date, F.data.startswith("cal:prev:"))
async def cb_cal_prev(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")[2].split("-")
    year, month = int(parts[0]), int(parts[1])
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(year, month))
    await callback.answer()


@router.callback_query(BroadcastFSM.picking_date, F.data.startswith("cal:next:"))
async def cb_cal_next(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")[2].split("-")
    year, month = int(parts[0]), int(parts[1])
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(year, month))
    await callback.answer()


@router.callback_query(BroadcastFSM.picking_date, F.data == "cal:ignore")
@router.callback_query(BroadcastFSM.picking_hour, F.data == "cal:ignore")
@router.callback_query(BroadcastFSM.picking_minute, F.data == "cal:ignore")
async def cb_cal_ignore(callback: CallbackQuery) -> None:
    await callback.answer()


# --------------- Day selection ---------------

@router.callback_query(BroadcastFSM.picking_date, F.data.startswith("cal:day:"))
async def cb_cal_day(callback: CallbackQuery, state: FSMContext) -> None:
    date_str = callback.data.split(":")[2]
    await state.set_state(BroadcastFSM.picking_hour)
    await callback.message.edit_text(
        "🕐 Выберите час публикации:",
        reply_markup=hour_kb(date_str),
    )
    await callback.answer()


# --------------- Hour selection ---------------

@router.callback_query(BroadcastFSM.picking_hour, F.data.startswith("cal:hour:"))
async def cb_cal_hour(callback: CallbackQuery, state: FSMContext) -> None:
    # cal:hour:YYYY-MM-DD:HH
    parts = callback.data.split(":")
    date_str = parts[2]
    hour = int(parts[3])
    await state.set_state(BroadcastFSM.picking_minute)
    await callback.message.edit_text(
        "🕐 Выберите минуты:",
        reply_markup=minute_kb(date_str, hour),
    )
    await callback.answer()


@router.callback_query(BroadcastFSM.picking_hour, F.data.startswith("cal:back_to_cal:"))
async def cb_back_to_cal(callback: CallbackQuery, state: FSMContext) -> None:
    date_str = callback.data.split(":")[3]
    d = datetime.strptime(date_str, "%Y-%m-%d")
    await state.set_state(BroadcastFSM.picking_date)
    await callback.message.edit_text(
        "📅 Выберите дату публикации:",
        reply_markup=calendar_kb(d.year, d.month),
    )
    await callback.answer()


# --------------- Minute selection (finalize) ---------------

@router.callback_query(BroadcastFSM.picking_minute, F.data.startswith("cal:min:"))
async def cb_cal_minute(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    # cal:min:YYYY-MM-DD:HH:MM
    parts = callback.data.split(":")
    date_str = parts[2]
    hour = int(parts[3])
    minute = int(parts[4])

    tz = pytz.timezone(settings.timezone)
    naive_dt = datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")
    aware_dt = tz.localize(naive_dt)

    now = datetime.now(tz)
    if aware_dt <= now:
        await callback.answer("❌ Это время уже прошло, выберите другое", show_alert=True)
        return

    data = await state.get_data()
    selected = list(data.get("selected_channels", []))

    admin_repo = AdminRepo(session)
    admin = await admin_repo.get_by_telegram_id(callback.from_user.id)

    post_repo = ScheduledPostRepo(session)
    post = await post_repo.create(
        content_type=data["content_type"],
        text=data.get("text"),
        media_file_id=data.get("media_file_id"),
        caption=data.get("caption"),
        target_channels=selected,
        publish_at=aware_dt,
        created_by=admin.id,
    )

    schedule_post(post.id, aware_dt)

    channel_repo = ChannelRepo(session)
    channels = await channel_repo.get_all(active_only=True)
    id_to_title = {ch.id: ch.title for ch in channels}
    ch_names = ", ".join(id_to_title.get(cid, str(cid)) for cid in selected)

    await callback.message.edit_text(
        f"✅ Пост запланирован!\n\n"
        f"⏰ Время: {aware_dt.strftime('%d.%m.%Y %H:%M')} ({settings.timezone})\n"
        f"📢 Каналы: {ch_names}\n"
        f"📎 Тип: {data['content_type']}",
        reply_markup=MAIN_MENU,
    )
    await state.clear()
    await callback.answer()


@router.callback_query(BroadcastFSM.picking_minute, F.data.startswith("cal:back_to_hour:"))
async def cb_back_to_hour(callback: CallbackQuery, state: FSMContext) -> None:
    date_str = callback.data.split(":")[3]
    await state.set_state(BroadcastFSM.picking_hour)
    await callback.message.edit_text(
        "🕐 Выберите час публикации:",
        reply_markup=hour_kb(date_str),
    )
    await callback.answer()


# --------------- Cancel from any calendar screen ---------------

@router.callback_query(BroadcastFSM.picking_date, F.data == "cal:cancel")
@router.callback_query(BroadcastFSM.picking_hour, F.data == "cal:cancel")
@router.callback_query(BroadcastFSM.picking_minute, F.data == "cal:cancel")
async def cb_cal_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Планирование отменено.", reply_markup=MAIN_MENU)
    await callback.answer()


# --------------- Scheduled posts list/detail/cancel ---------------

@router.callback_query(F.data == "schedule:list")
async def cb_schedule_list(
    callback: CallbackQuery, session: AsyncSession, is_admin: bool
) -> None:
    if not is_admin:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    repo = ScheduledPostRepo(session)
    posts = await repo.get_pending()
    if not posts:
        await callback.message.edit_text(
            "⏰ Нет отложенных постов.", reply_markup=MAIN_MENU
        )
    else:
        await callback.message.edit_text(
            "⏰ Отложенные посты:", reply_markup=scheduled_list_kb(posts)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("schedule:detail:"))
async def cb_schedule_detail(
    callback: CallbackQuery, session: AsyncSession, is_admin: bool
) -> None:
    if not is_admin:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    post_id = int(callback.data.split(":")[2])
    repo = ScheduledPostRepo(session)
    post = await repo.get_by_id(post_id)
    if post is None:
        await callback.answer("Пост не найден", show_alert=True)
        return

    channel_repo = ChannelRepo(session)
    channels = await channel_repo.get_all()
    id_to_title = {ch.id: ch.title for ch in channels}
    ch_names = ", ".join(id_to_title.get(cid, str(cid)) for cid in post.target_channels)

    text = (
        f"📋 <b>Отложенный пост #{post.id}</b>\n\n"
        f"📎 Тип: {post.content_type}\n"
        f"⏰ Публикация: {post.publish_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📢 Каналы: {ch_names}\n"
        f"📊 Статус: {post.status}"
    )
    if post.text:
        text += f"\n\n📝 Текст: {post.text[:300]}"
    if post.caption:
        text += f"\n📝 Подпись: {post.caption[:300]}"

    kb = scheduled_detail_kb(post.id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("schedule:cancel:"))
async def cb_schedule_cancel(
    callback: CallbackQuery, session: AsyncSession, is_admin: bool
) -> None:
    if not is_admin:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    post_id = int(callback.data.split(":")[2])
    repo = ScheduledPostRepo(session)
    cancelled = await repo.cancel(post_id)
    if cancelled:
        cancel_scheduled_job(post_id)
        await callback.answer("✅ Пост отменён")
    else:
        await callback.answer("❌ Не удалось отменить пост", show_alert=True)

    posts = await repo.get_pending()
    if not posts:
        await callback.message.edit_text(
            "⏰ Нет отложенных постов.", reply_markup=MAIN_MENU
        )
    else:
        await callback.message.edit_text(
            "⏰ Отложенные посты:", reply_markup=scheduled_list_kb(posts)
        )


@router.callback_query(F.data.startswith("schedule:delete:"))
async def cb_schedule_delete(
    callback: CallbackQuery, session: AsyncSession, is_admin: bool
) -> None:
    if not is_admin:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    post_id = int(callback.data.split(":")[2])
    cancel_scheduled_job(post_id)
    repo = ScheduledPostRepo(session)
    deleted = await repo.delete_by_id(post_id)
    if deleted:
        await callback.answer("🗑 Пост удалён")
    else:
        await callback.answer("❌ Пост не найден", show_alert=True)

    posts = await repo.get_pending()
    if not posts:
        await callback.message.edit_text(
            "⏰ Нет отложенных постов.", reply_markup=MAIN_MENU
        )
    else:
        await callback.message.edit_text(
            "⏰ Отложенные посты:", reply_markup=scheduled_list_kb(posts)
        )
