"""Budget model."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.category import Category

from app.database import Base


class Budget(Base):
    """A spending or income budget for a period, optionally category-scoped."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    period_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    amount_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # minor units
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.utcnow
    )

    category: Mapped[Category | None] = relationship("Category", back_populates="budgets")

    __table_args__ = (
        Index("ix_budgets_period", "period_start", "period_end"),
        Index("ix_budgets_category_period", "category_id", "period_start", "period_end"),
        CheckConstraint("amount_limit >= 0", name="ck_budgets_amount_limit_non_negative"),
        CheckConstraint("period_end >= period_start", name="ck_budgets_period_order"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Budget id={self.id} category_id={self.category_id} limit={self.amount_limit}>"
