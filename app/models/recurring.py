"""Recurring transaction model."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.category import Category

from app.database import Base


class RecurringTransaction(Base):
    """A rule that generates transactions on a repeating schedule."""

    __tablename__ = "recurring_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # income, expense, transfer
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # daily, weekly, monthly, yearly, custom
    interval_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    next_run_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.utcnow
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )

    account: Mapped[Account] = relationship("Account")
    category: Mapped[Category | None] = relationship("Category")

    __table_args__ = (
        Index("ix_recurring_active_next", "is_active", "next_run_date"),
        CheckConstraint("amount > 0", name="ck_recurring_amount_positive"),
        CheckConstraint(
            "interval IN ('daily', 'weekly', 'monthly', 'yearly', 'custom')",
            name="ck_recurring_interval",
        ),
        CheckConstraint("type IN ('income', 'expense', 'transfer')", name="ck_recurring_type"),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_recurring_end_after_start",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<RecurringTransaction id={self.id} interval={self.interval!r} next={self.next_run_date!r}>"
