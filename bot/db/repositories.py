from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Admin, Channel, ScheduledPost


class AdminRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> Admin | None:
        result = await self.session.execute(
            select(Admin).where(Admin.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[Admin]:
        result = await self.session.execute(select(Admin).order_by(Admin.created_at))
        return list(result.scalars().all())

    async def create(self, telegram_id: int, username: str | None, role: str = "admin") -> Admin:
        admin = Admin(telegram_id=telegram_id, username=username, role=role)
        self.session.add(admin)
        await self.session.commit()
        await self.session.refresh(admin)
        return admin

    async def delete_by_telegram_id(self, telegram_id: int) -> bool:
        result = await self.session.execute(
            delete(Admin).where(Admin.telegram_id == telegram_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def update_username(self, telegram_id: int, username: str | None) -> None:
        await self.session.execute(
            update(Admin)
            .where(Admin.telegram_id == telegram_id)
            .values(username=username)
        )
        await self.session.commit()

    async def is_admin(self, telegram_id: int) -> bool:
        admin = await self.get_by_telegram_id(telegram_id)
        return admin is not None

    async def is_superadmin(self, telegram_id: int) -> bool:
        admin = await self.get_by_telegram_id(telegram_id)
        return admin is not None and admin.role == "superadmin"


class ChannelRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self, active_only: bool = False) -> list[Channel]:
        query = select(Channel).order_by(Channel.created_at)
        if active_only:
            query = query.where(Channel.is_active.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_chat_id(self, chat_id: int) -> Channel | None:
        result = await self.session.execute(
            select(Channel).where(Channel.telegram_chat_id == chat_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, channel_id: int) -> Channel | None:
        result = await self.session.execute(
            select(Channel).where(Channel.id == channel_id)
        )
        return result.scalar_one_or_none()

    async def create(self, chat_id: int, title: str, added_by: int) -> Channel:
        channel = Channel(telegram_chat_id=chat_id, title=title, added_by=added_by)
        self.session.add(channel)
        await self.session.commit()
        await self.session.refresh(channel)
        return channel

    async def toggle_active(self, channel_id: int) -> Channel | None:
        channel = await self.get_by_id(channel_id)
        if channel is None:
            return None
        channel.is_active = not channel.is_active
        await self.session.commit()
        await self.session.refresh(channel)
        return channel

    async def delete_by_id(self, channel_id: int) -> bool:
        result = await self.session.execute(
            delete(Channel).where(Channel.id == channel_id)
        )
        await self.session.commit()
        return result.rowcount > 0


class ScheduledPostRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        content_type: str,
        text: str | None,
        media_file_id: str | None,
        caption: str | None,
        target_channels: list[int],
        publish_at: datetime,
        created_by: int,
    ) -> ScheduledPost:
        post = ScheduledPost(
            content_type=content_type,
            text=text,
            media_file_id=media_file_id,
            caption=caption,
            target_channels=target_channels,
            publish_at=publish_at,
            created_by=created_by,
        )
        self.session.add(post)
        await self.session.commit()
        await self.session.refresh(post)
        return post

    async def get_pending(self) -> list[ScheduledPost]:
        result = await self.session.execute(
            select(ScheduledPost)
            .where(ScheduledPost.status == "pending")
            .order_by(ScheduledPost.publish_at)
        )
        return list(result.scalars().all())

    async def get_by_id(self, post_id: int) -> ScheduledPost | None:
        result = await self.session.execute(
            select(ScheduledPost).where(ScheduledPost.id == post_id)
        )
        return result.scalar_one_or_none()

    async def mark_published(self, post_id: int) -> None:
        await self.session.execute(
            update(ScheduledPost)
            .where(ScheduledPost.id == post_id)
            .values(status="published")
        )
        await self.session.commit()

    async def mark_failed(self, post_id: int) -> None:
        await self.session.execute(
            update(ScheduledPost)
            .where(ScheduledPost.id == post_id)
            .values(status="failed")
        )
        await self.session.commit()

    async def cancel(self, post_id: int) -> bool:
        result = await self.session.execute(
            update(ScheduledPost)
            .where(ScheduledPost.id == post_id, ScheduledPost.status == "pending")
            .values(status="cancelled")
        )
        await self.session.commit()
        return result.rowcount > 0

    async def delete_by_id(self, post_id: int) -> bool:
        result = await self.session.execute(
            delete(ScheduledPost).where(ScheduledPost.id == post_id)
        )
        await self.session.commit()
        return result.rowcount > 0
