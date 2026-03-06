import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime

import pytz

from bot.config import settings
from bot.db.repositories import ChannelRepo
from bot.keyboards.calendar import calendar_kb
from bot.keyboards.inline import BACK_TO_MENU, MAIN_MENU, channel_select_kb
from bot.services.broadcaster import broadcast_to_channels
from bot.states.broadcast import BroadcastFSM

logger = logging.getLogger(__name__)

router = Router()


def _extract_content(message: Message) -> dict | None:
    """Extract sendable content from a user message (including forwarded)."""
    if message.photo:
        return {
            "content_type": "photo",
            "media_file_id": message.photo[-1].file_id,
            "caption": message.caption,
            "text": None,
        }
    if message.video:
        return {
            "content_type": "video",
            "media_file_id": message.video.file_id,
            "caption": message.caption,
            "text": None,
        }
    if message.document:
        return {
            "content_type": "document",
            "media_file_id": message.document.file_id,
            "caption": message.caption,
            "text": None,
        }
    if message.animation:
        return {
            "content_type": "animation",
            "media_file_id": message.animation.file_id,
            "caption": message.caption,
            "text": None,
        }
    if message.sticker:
        return {
            "content_type": "sticker",
            "media_file_id": message.sticker.file_id,
            "caption": None,
            "text": None,
        }
    if message.voice:
        return {
            "content_type": "voice",
            "media_file_id": message.voice.file_id,
            "caption": message.caption,
            "text": None,
        }
    if message.video_note:
        return {
            "content_type": "video_note",
            "media_file_id": message.video_note.file_id,
            "caption": None,
            "text": None,
        }
    if message.text:
        return {
            "content_type": "text",
            "media_file_id": None,
            "caption": None,
            "text": message.text,
        }
    return None


def _get_selected(data: dict) -> set[int]:
    return set(data.get("selected_channels") or [])


@router.callback_query(F.data == "broadcast:start")
async def cb_broadcast_start(
    callback: CallbackQuery, is_admin: bool, state: FSMContext
) -> None:
    if not is_admin:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(BroadcastFSM.waiting_content)
    await callback.message.edit_text(
        "📨 <b>Новая рассылка</b>\n\n"
        "Отправьте сообщение для рассылки: текст, фото, видео, документ, "
        "анимацию или перешлите (forward) любое сообщение.",
        parse_mode="HTML",
        reply_markup=BACK_TO_MENU,
    )
    await callback.answer()


@router.message(BroadcastFSM.waiting_content)
async def process_broadcast_content(
    message: Message, session: AsyncSession, is_admin: bool, state: FSMContext
) -> None:
    if not is_admin:
        await state.clear()
        return

    content = _extract_content(message)
    if content is None:
        await message.answer("❌ Неподдерживаемый тип контента. Попробуйте снова.")
        return

    await state.update_data(**content, selected_channels=[])

    repo = ChannelRepo(session)
    channels = await repo.get_all(active_only=True)

    if not channels:
        await message.answer(
            "❌ Нет подключённых активных каналов. Сначала добавьте каналы.",
            reply_markup=BACK_TO_MENU,
        )
        await state.clear()
        return

    preview_parts = []
    ct = content["content_type"]
    if ct == "text":
        preview_parts.append(f"📝 Текст: {content['text'][:200]}")
    elif ct in ("photo", "video", "document", "animation", "voice"):
        emoji_map = {
            "photo": "🖼", "video": "🎬", "document": "📄",
            "animation": "🎞", "voice": "🎤",
        }
        preview_parts.append(f"{emoji_map.get(ct, '📎')} Тип: {ct}")
        if content.get("caption"):
            preview_parts.append(f"Подпись: {content['caption'][:200]}")
    else:
        preview_parts.append(f"📎 Тип: {ct}")

    preview_text = "\n".join(preview_parts)

    await state.set_state(BroadcastFSM.choosing_channels)
    kb = channel_select_kb(channels, set())
    await message.answer(
        f"✅ Контент получен!\n\n{preview_text}\n\n"
        "Выберите каналы для рассылки:",
        reply_markup=kb,
    )


@router.callback_query(BroadcastFSM.choosing_channels, F.data.startswith("bcast:toggle_ch:"))
async def cb_toggle_channel_selection(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    channel_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    selected = _get_selected(data)

    if channel_id in selected:
        selected.discard(channel_id)
    else:
        selected.add(channel_id)
    await state.update_data(selected_channels=list(selected))

    repo = ChannelRepo(session)
    channels = await repo.get_all(active_only=True)
    kb = channel_select_kb(channels, selected)

    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(BroadcastFSM.choosing_channels, F.data == "bcast:select_all")
async def cb_select_all(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    repo = ChannelRepo(session)
    channels = await repo.get_all(active_only=True)
    selected = {ch.id for ch in channels}
    await state.update_data(selected_channels=list(selected))
    kb = channel_select_kb(channels, selected)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(BroadcastFSM.choosing_channels, F.data == "bcast:deselect_all")
async def cb_deselect_all(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    await state.update_data(selected_channels=[])
    repo = ChannelRepo(session)
    channels = await repo.get_all(active_only=True)
    kb = channel_select_kb(channels, set())
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(BroadcastFSM.choosing_channels, F.data == "bcast:send_now")
async def cb_send_now(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    data = await state.get_data()
    selected = _get_selected(data)

    if not selected:
        await callback.answer("❌ Выберите хотя бы один канал", show_alert=True)
        return

    repo = ChannelRepo(session)
    channels = await repo.get_all(active_only=True)
    id_to_chat = {ch.id: ch.telegram_chat_id for ch in channels}
    id_to_title = {ch.id: ch.title for ch in channels}

    target_chat_ids = [id_to_chat[cid] for cid in selected if cid in id_to_chat]

    await callback.message.edit_text("⏳ Отправка...")
    await callback.answer()

    results = await broadcast_to_channels(
        bot,
        target_chat_ids,
        data["content_type"],
        data.get("text"),
        data.get("media_file_id"),
        data.get("caption"),
    )

    chat_to_id = {v: k for k, v in id_to_chat.items()}
    success = sum(1 for v in results.values() if v)
    failed = len(results) - success

    report_lines = ["📊 <b>Результат рассылки:</b>\n"]
    for chat_id, ok in results.items():
        ch_id = chat_to_id.get(chat_id)
        name = id_to_title.get(ch_id, str(chat_id))
        status = "✅" if ok else "❌"
        report_lines.append(f"{status} {name}")
    report_lines.append(f"\nИтого: {success} успешно, {failed} ошибок")

    await callback.message.edit_text(
        "\n".join(report_lines),
        parse_mode="HTML",
        reply_markup=MAIN_MENU,
    )
    await state.clear()


@router.callback_query(BroadcastFSM.choosing_channels, F.data == "bcast:schedule")
async def cb_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected = _get_selected(data)
    if not selected:
        await callback.answer("❌ Выберите хотя бы один канал", show_alert=True)
        return
    tz = pytz.timezone(settings.timezone)
    now = datetime.now(tz)
    await state.set_state(BroadcastFSM.picking_date)
    await callback.message.edit_text(
        "📅 Выберите дату публикации:",
        reply_markup=calendar_kb(now.year, now.month),
    )
    await callback.answer()


@router.callback_query(BroadcastFSM.choosing_channels, F.data == "bcast:cancel")
async def cb_cancel_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "❌ Рассылка отменена.",
        reply_markup=MAIN_MENU,
    )
    await callback.answer()
