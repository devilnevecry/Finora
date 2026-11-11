"""Category repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.transaction import Transaction


class CategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.flush()
        await self.session.refresh(category)
        return category

    async def get(self, category_id: int) -> Category | None:
        result = await self.session.execute(select(Category).where(Category.id == category_id))
        return result.scalar_one_or_none()

    async def get_by_name_type(self, name: str, type: str) -> Category | None:
        result = await self.session.execute(
            select(Category).where(Category.name == name, Category.type == type)
        )
        return result.scalar_one_or_none()

    async def list(
        self, type: str | None = None, include_archived: bool = False
    ) -> Sequence[Category]:
        stmt = select(Category).order_by(Category.name)
        if type:
            stmt = stmt.where(Category.type == type)
        if not include_archived:
            stmt = stmt.where(Category.is_archived == False)  # noqa: E712
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, category_id: int, **fields) -> Category | None:
        category = await self.get(category_id)
        if category is None:
            return None
        for key, value in fields.items():
            if hasattr(category, key):
                setattr(category, key, value)
        await self.session.flush()
        await self.session.refresh(category)
        return category

    async def delete(self, category_id: int) -> bool:
        category = await self.get(category_id)
        if category is None:
            return False
        await self.session.delete(category)
        await self.session.flush()
        return True

    async def archive(self, category_id: int) -> Category | None:
        return await self.update(category_id, is_archived=True)

    async def has_transactions(self, category_id: int) -> bool:
        result = await self.session.execute(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.category_id == category_id)
        )
        return (result.scalar_one() or 0) > 0
