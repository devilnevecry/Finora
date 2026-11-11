"""Category model."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.budget import Budget
    from app.models.transaction import Transaction

from app.database import Base


class Category(Base):
    """Income or expense category with optional color/icon and archive state."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # income or expense
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.utcnow
    )

    transactions: Mapped[list[Transaction]] = relationship("Transaction", back_populates="category")
    budgets: Mapped[list[Budget]] = relationship(
        "Budget", back_populates="category", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_categories_type", "type"),
        Index("ix_categories_is_archived", "is_archived"),
        UniqueConstraint("name", "type", name="uq_categories_name_type"),
        CheckConstraint("type IN ('income', 'expense')", name="ck_categories_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Category id={self.id} name={self.name!r} type={self.type!r}>"
