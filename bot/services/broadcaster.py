import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter

logger = logging.getLogger(__name__)

SEND_INTERVAL = 0.05  # 20 messages/sec (under Telegram's 30/sec limit)


async def send_content_to_channel(
    bot: Bot,
    chat_id: int,
    content_type: str,
    text: str | None = None,
    media_file_id: str | None = None,
    caption: str | None = None,
) -> bool:
    try:
        match content_type:
            case "text":
                await bot.send_message(chat_id, text or "")
            case "photo":
                await bot.send_photo(chat_id, media_file_id, caption=caption)
            case "video":
                await bot.send_video(chat_id, media_file_id, caption=caption)
            case "document":
                await bot.send_document(chat_id, media_file_id, caption=caption)
            case "animation":
                await bot.send_animation(chat_id, media_file_id, caption=caption)
            case "sticker":
                await bot.send_sticker(chat_id, media_file_id)
            case "voice":
                await bot.send_voice(chat_id, media_file_id, caption=caption)
            case "video_note":
                await bot.send_video_note(chat_id, media_file_id)
            case _:
                logger.warning("Unknown content_type: %s", content_type)
                return False
        return True
    except TelegramRetryAfter as e:
        logger.warning("Rate limited, sleeping %s seconds", e.retry_after)
        await asyncio.sleep(e.retry_after)
        return await send_content_to_channel(
            bot, chat_id, content_type, text, media_file_id, caption
        )
    except Exception:
        logger.exception("Failed to send to channel %s", chat_id)
        return False


async def broadcast_to_channels(
    bot: Bot,
    channel_chat_ids: list[int],
    content_type: str,
    text: str | None = None,
    media_file_id: str | None = None,
    caption: str | None = None,
) -> dict[int, bool]:
    """Send content to multiple channels. Returns {chat_id: success}."""
    results: dict[int, bool] = {}
    for chat_id in channel_chat_ids:
        ok = await send_content_to_channel(
            bot, chat_id, content_type, text, media_file_id, caption
        )
        results[chat_id] = ok
        await asyncio.sleep(SEND_INTERVAL)
    return results
