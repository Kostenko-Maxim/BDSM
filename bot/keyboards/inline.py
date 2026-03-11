from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestChat,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.models import Channel, ScheduledPost
from bot.utils import format_datetime_local

REMOVE_REPLY_KB = ReplyKeyboardRemove()


def channel_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📢 Выбрать канал",
                    request_chat=KeyboardButtonRequestChat(
                        request_id=1,
                        chat_is_channel=True,
                        bot_is_member=True,
                    ),
                )
            ],
            [KeyboardButton(text="✅ Готово")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

MAIN_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📨 Новая рассылка", callback_data="broadcast:start")],
        [InlineKeyboardButton(text="📢 Каналы", callback_data="channels:list")],
        [InlineKeyboardButton(text="⏰ Отложенные посты", callback_data="schedule:list")],
        [InlineKeyboardButton(text="👥 Админы", callback_data="admin:list")],
    ]
)


def admin_list_kb(admins: list, superadmin_id: int, is_superadmin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for admin in admins:
        role_icon = "👑" if admin.role == "superadmin" else "👤"
        name = admin.username or str(admin.telegram_id)
        builder.row(
            InlineKeyboardButton(
                text=f"{role_icon} {name}",
                callback_data=f"admin:info:{admin.telegram_id}",
            )
        )
    if is_superadmin:
        builder.row(
            InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin:add")
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main"))
    return builder.as_markup()


def admin_detail_kb(admin_tg_id: int, is_superadmin_viewer: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_superadmin_viewer:
        builder.row(
            InlineKeyboardButton(
                text="🗑 Удалить", callback_data=f"admin:delete:{admin_tg_id}"
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 К списку", callback_data="admin:list"))
    return builder.as_markup()


def channel_list_kb(channels: list[Channel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        status = "✅" if ch.is_active else "❌"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {ch.title}", callback_data=f"channels:detail:{ch.id}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить канал", callback_data="channels:add")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main"))
    return builder.as_markup()


def channel_detail_kb(channel: Channel) -> InlineKeyboardMarkup:
    toggle_text = "❌ Отключить" if channel.is_active else "✅ Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_text, callback_data=f"channels:toggle:{channel.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить", callback_data=f"channels:delete:{channel.id}"
                )
            ],
            [InlineKeyboardButton(text="🔙 К списку", callback_data="channels:list")],
        ]
    )


def channel_select_kb(
    channels: list[Channel], selected_ids: set[int]
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        mark = "☑" if ch.id in selected_ids else "☐"
        builder.row(
            InlineKeyboardButton(
                text=f"{mark} {ch.title}",
                callback_data=f"bcast:toggle_ch:{ch.id}",
            )
        )
    if channels:
        builder.row(
            InlineKeyboardButton(text="✅ Выбрать все", callback_data="bcast:select_all"),
            InlineKeyboardButton(text="☐ Сбросить", callback_data="bcast:deselect_all"),
        )
    builder.row(
        InlineKeyboardButton(text="📤 Отправить сейчас", callback_data="bcast:send_now"),
        InlineKeyboardButton(text="⏰ Отложить", callback_data="bcast:schedule"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="bcast:cancel"))
    return builder.as_markup()


BACK_TO_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")]
    ]
)


def scheduled_list_kb(posts: list[ScheduledPost]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for post in posts:
        time_str = format_datetime_local(post.publish_at)
        label = f"⏰ {time_str} — {post.content_type}"
        builder.row(
            InlineKeyboardButton(
                text=label, callback_data=f"schedule:detail:{post.id}"
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main"))
    return builder.as_markup()


def scheduled_detail_kb(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить пост", callback_data=f"schedule:cancel:{post_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить пост", callback_data=f"schedule:delete:{post_id}"
                )
            ],
            [InlineKeyboardButton(text="🔙 К списку", callback_data="schedule:list")],
        ]
    )
