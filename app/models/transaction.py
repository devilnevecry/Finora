"""Transaction model."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
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
    from app.models.tag import TransactionTag

from app.database import Base


class Transaction(Base):
    """A single financial movement: income, expense, or transfer."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # minor units, positive
    transaction_date: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # income, expense, transfer
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated legacy field
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.utcnow
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )
    linked_transaction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    account: Mapped[Account] = relationship("Account", back_populates="transactions")
    category: Mapped[Category | None] = relationship("Category", back_populates="transactions")
    tags_rel: Mapped[list[TransactionTag]] = relationship(
        "TransactionTag", back_populates="transaction", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_transactions_account_date", "account_id", "transaction_date"),
        Index("ix_transactions_type_date", "type", "transaction_date"),
        Index("ix_transactions_category_date", "category_id", "transaction_date"),
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint("type IN ('income', 'expense', 'transfer')", name="ck_transactions_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Transaction id={self.id} type={self.type!r} "
            f"amount={self.amount} date={self.transaction_date!r}>"
        )
