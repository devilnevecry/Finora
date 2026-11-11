"""Category service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.repositories.category_repository import CategoryRepository

VALID_CATEGORY_TYPES = {"income", "expense"}


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.categories = CategoryRepository(session)

    async def create(
        self, *, name: str, type: str, color: str | None = None, icon: str | None = None
    ) -> Category:
        name = (name or "").strip()
        if not name:
            raise ValueError("category name is required")
        if type not in VALID_CATEGORY_TYPES:
            raise ValueError(f"invalid category type: {type}")
        existing = await self.categories.get_by_name_type(name, type)
        if existing:
            raise ValueError(f"category '{name}' already exists for type '{type}'")
        category = Category(
            name=name,
            type=type,
            color=color,
            icon=icon,
            is_archived=False,
            created_at=datetime.utcnow(),
        )
        return await self.categories.add(category)

    async def list(self, type: str | None = None, include_archived: bool = False):
        return await self.categories.list(type=type, include_archived=include_archived)

    async def get(self, category_id: int) -> Category | None:
        return await self.categories.get(category_id)

    async def update(
        self,
        category_id: int,
        *,
        name: str | None = None,
        type: str | None = None,
        color: str | None = None,
        icon: str | None = None,
        is_archived: bool | None = None,
    ) -> Category | None:
        category = await self.categories.get(category_id)
        if category is None:
            return None
        fields = {}
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("category name is required")
            fields["name"] = name
        if type is not None:
            if type not in VALID_CATEGORY_TYPES:
                raise ValueError(f"invalid category type: {type}")
            fields["type"] = type
        if color is not None:
            fields["color"] = color or None
        if icon is not None:
            fields["icon"] = icon or None
        if is_archived is not None:
            fields["is_archived"] = is_archived
        return await self.categories.update(category_id, **fields)

    async def archive(self, category_id: int) -> Category | None:
        return await self.categories.archive(category_id)

    async def delete(self, category_id: int) -> bool:
        return await self.categories.delete(category_id)
