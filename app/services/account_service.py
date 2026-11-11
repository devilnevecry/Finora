"""Account service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.account import Account
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.currency import MoneyError, to_minor_units, validate_non_negative

settings = get_settings()

VALID_ACCOUNT_TYPES = {"cash", "bank", "savings", "credit", "custom"}


class AccountService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.accounts = AccountRepository(session)
        self.transactions = TransactionRepository(session)

    async def create(
        self,
        *,
        name: str,
        type: str,
        currency: str | None = None,
        opening_balance,
        description: str | None = None,
    ) -> Account:
        name = (name or "").strip()
        if not name:
            raise MoneyError("account name is required")
        if type not in VALID_ACCOUNT_TYPES:
            raise MoneyError(f"invalid account type: {type}")
        currency = (currency or settings.base_currency).upper()
        if len(currency) != 3:
            raise MoneyError("currency must be a 3-letter code")
        opening_minor = to_minor_units(opening_balance)
        validate_non_negative(opening_minor, "opening balance")

        account = Account(
            name=name,
            type=type,
            currency=currency,
            opening_balance=opening_minor,
            current_balance=opening_minor,
            description=description or None,
            created_at=datetime.utcnow(),
            is_active=True,
            is_archived=False,
        )
        return await self.accounts.add(account)

    async def list(self, include_archived: bool = False):
        return await self.accounts.list(include_archived=include_archived)

    async def get(self, account_id: int) -> Account | None:
        return await self.accounts.get(account_id)

    async def update(
        self,
        account_id: int,
        *,
        name: str | None = None,
        type: str | None = None,
        currency: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
        is_archived: bool | None = None,
    ) -> Account | None:
        account = await self.accounts.get(account_id)
        if account is None:
            return None
        fields = {}
        if name is not None:
            name = name.strip()
            if not name:
                raise MoneyError("account name is required")
            fields["name"] = name
        if type is not None:
            if type not in VALID_ACCOUNT_TYPES:
                raise MoneyError(f"invalid account type: {type}")
            fields["type"] = type
        if currency is not None:
            currency = currency.upper()
            if len(currency) != 3:
                raise MoneyError("currency must be a 3-letter code")
            fields["currency"] = currency
        if description is not None:
            fields["description"] = description or None
        if is_active is not None:
            fields["is_active"] = is_active
        if is_archived is not None:
            fields["is_archived"] = is_archived
        return await self.accounts.update(account_id, **fields)

    async def delete(self, account_id: int) -> bool:
        return await self.accounts.delete(account_id)

    async def archive(self, account_id: int) -> Account | None:
        return await self.accounts.archive(account_id)
