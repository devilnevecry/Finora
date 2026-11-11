"""Account model."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.transaction import Transaction

from app.database import Base


class Account(Base):
    """A financial account holding a balance in the base currency."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # cash, bank, savings, credit, custom
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    opening_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.utcnow
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_accounts_is_active", "is_active"),
        Index("ix_accounts_is_archived", "is_archived"),
        CheckConstraint("length(currency) = 3", name="ck_accounts_currency_length"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Account id={self.id} name={self.name!r} balance={self.current_balance}>"
