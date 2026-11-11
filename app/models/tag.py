"""Tag model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.transaction import Transaction

from app.database import Base


class Tag(Base):
    """User-defined tag for classifying transactions."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)

    transactions: Mapped[list[TransactionTag]] = relationship(
        "TransactionTag", back_populates="tag", cascade="all, delete-orphan"
    )


class TransactionTag(Base):
    """Many-to-many association between transactions and tags."""

    __tablename__ = "transaction_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True
    )

    transaction: Mapped[Transaction] = relationship("Transaction", back_populates="tags_rel")
    tag: Mapped[Tag] = relationship("Tag", back_populates="transactions")

    __table_args__ = (UniqueConstraint("transaction_id", "tag_id", name="uq_transaction_tags"),)
