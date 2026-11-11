"""Tag repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag


class TagRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, name: str) -> Tag:
        name = name.strip()
        if not name:
            raise ValueError("tag name must not be empty")
        result = await self.session.execute(
            select(Tag).where(func.lower(Tag.name) == func.lower(name))
        )
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(name=name)
            self.session.add(tag)
            await self.session.flush()
            await self.session.refresh(tag)
        return tag

    async def list(self) -> Sequence[Tag]:
        result = await self.session.execute(select(Tag).order_by(Tag.name))
        return result.scalars().all()

    async def get_by_id(self, tag_id: int) -> Tag | None:
        result = await self.session.execute(select(Tag).where(Tag.id == tag_id))
        return result.scalar_one_or_none()
