import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from bot.config import settings
from bot.db.engine import async_session
from bot.db.repositories import ChannelRepo, ScheduledPostRepo
from bot.services.broadcaster import broadcast_to_channels

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.timezone)


async def execute_scheduled_post(post_id: int) -> None:
    from bot.loader import bot as bot_instance

    async with async_session() as session:
        post_repo = ScheduledPostRepo(session)
        channel_repo = ChannelRepo(session)

        post = await post_repo.get_by_id(post_id)
        if post is None or post.status != "pending":
            return

        all_channels = await channel_repo.get_all(active_only=True)
        id_to_chat = {ch.id: ch.telegram_chat_id for ch in all_channels}

        target_chat_ids = [
            id_to_chat[ch_id]
            for ch_id in post.target_channels
            if ch_id in id_to_chat
        ]

        if not target_chat_ids:
            await post_repo.mark_failed(post_id)
            logger.warning("No active channels for post %s", post_id)
            return

        results = await broadcast_to_channels(
            bot_instance,
            target_chat_ids,
            post.content_type,
            post.text,
            post.media_file_id,
            post.caption,
        )

        if all(results.values()):
            await post_repo.mark_published(post_id)
            logger.info("Post %s published successfully", post_id)
        else:
            await post_repo.mark_failed(post_id)
            failed = [cid for cid, ok in results.items() if not ok]
            logger.warning("Post %s partially failed: %s", post_id, failed)


def schedule_post(post_id: int, run_at: datetime) -> None:
    scheduler.add_job(
        execute_scheduled_post,
        trigger=DateTrigger(run_date=run_at),
        args=[post_id],
        id=f"post_{post_id}",
        replace_existing=True,
    )
    logger.info("Scheduled post %s at %s", post_id, run_at)


def cancel_scheduled_job(post_id: int) -> None:
    job_id = f"post_{post_id}"
    job = scheduler.get_job(job_id)
    if job:
        scheduler.remove_job(job_id)
        logger.info("Cancelled scheduled job %s", job_id)


async def restore_pending_jobs() -> None:
    """Restore pending posts from DB on bot startup."""
    async with async_session() as session:
        repo = ScheduledPostRepo(session)
        pending = await repo.get_pending()
        now = datetime.now().astimezone()
        restored = 0
        for post in pending:
            if post.publish_at > now:
                schedule_post(post.id, post.publish_at)
                restored += 1
            else:
                await repo.mark_failed(post.id)
        logger.info("Restored %d scheduled jobs, expired %d", restored, len(pending) - restored)
