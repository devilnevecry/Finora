"""Transaction service — core financial logic.

Implements income, expense and transfer transactions with atomic balance
updates. Transfers are paired (expense on source, income on destination) and
are never counted as income or expense in analytics.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.repositories.account_repository import AccountRepository
from app.repositories.tag_repository import TagRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.currency import MoneyError, to_minor_units, validate_positive


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.transactions = TransactionRepository(session)
        self.accounts = AccountRepository(session)
        self.tags = TagRepository(session)

    def _parse_tags(self, tags) -> list[str]:
        if not tags:
            return []
        if isinstance(tags, str):
            raw = [t.strip() for t in tags.split(",")]
        else:
            raw = [str(t).strip() for t in tags]
        return [t for t in raw if t]

    async def _resolve_tag_ids(self, tag_names: Sequence[str]) -> list[int]:
        ids = []
        for name in tag_names:
            tag = await self.tags.get_or_create(name)
            ids.append(tag.id)
        return ids

    async def create_income(
        self,
        *,
        account_id: int,
        amount=None,
        transaction_date: datetime,
        description: str,
        category_id: int | None = None,
        notes: str | None = None,
        tags: Sequence[str] | None = None,
        amount_minor: int | None = None,
    ) -> Transaction:
        if amount is None and amount_minor is None:
            raise MoneyError("amount is required")
        return await self._create(
            type="income",
            account_id=account_id,
            amount=amount,
            amount_minor=amount_minor,
            transaction_date=transaction_date,
            description=description,
            category_id=category_id,
            notes=notes,
            tags=tags,
            adjust_balance_delta=+1,
        )

    async def create_expense(
        self,
        *,
        account_id: int,
        amount=None,
        transaction_date: datetime,
        description: str,
        category_id: int | None = None,
        notes: str | None = None,
        tags: Sequence[str] | None = None,
        amount_minor: int | None = None,
    ) -> Transaction:
        if amount is None and amount_minor is None:
            raise MoneyError("amount is required")
        return await self._create(
            type="expense",
            account_id=account_id,
            amount=amount,
            amount_minor=amount_minor,
            transaction_date=transaction_date,
            description=description,
            category_id=category_id,
            notes=notes,
            tags=tags,
            adjust_balance_delta=-1,
        )

    async def _create(
        self,
        *,
        type: str,
        account_id: int,
        amount,
        amount_minor: int | None,
        transaction_date: datetime,
        description: str,
        category_id: int | None,
        notes: str | None,
        tags: Sequence[str] | None,
        adjust_balance_delta: int,
    ) -> Transaction:
        if amount_minor is not None:
            minor = int(amount_minor)
        else:
            minor = to_minor_units(amount)
        validate_positive(minor, "amount")

        account = await self.accounts.get(account_id)
        if account is None:
            raise MoneyError(f"account {account_id} does not exist")
        if account.currency != account.currency:  # placeholder sanity
            pass

        if category_id is not None:
            from app.repositories.category_repository import CategoryRepository

            cats = CategoryRepository(self.session)
            category = await cats.get(category_id)
            if category is None:
                raise MoneyError(f"category {category_id} does not exist")
            # Category compatibility: income categories only with income, etc.
            if type in ("income", "expense") and category.type != type:
                raise MoneyError(f"category '{category.name}' is a {category.type} category")

        # Negative balance guard for non-credit accounts on expense/transfer out.
        if type == "expense" and account.type != "credit":
            if account.current_balance - minor < 0:
                raise MoneyError("insufficient funds")

        transaction = Transaction(
            account_id=account_id,
            category_id=category_id,
            amount=minor,
            transaction_date=transaction_date,
            type=type,
            description=description,
            notes=notes,
            tags=",".join(self._parse_tags(tags)) if tags else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            linked_transaction_id=None,
        )
        self.session.add(transaction)
        await self.session.flush()

        # update account balance
        account.current_balance += adjust_balance_delta * minor
        self.session.add(account)

        # tag associations
        tag_names = self._parse_tags(tags)
        if tag_names:
            tag_ids = await self._resolve_tag_ids(tag_names)
            for tag_id in tag_ids:
                self.session.add(
                    __import__("app.models.tag", fromlist=["TransactionTag"]).TransactionTag(
                        transaction_id=transaction.id, tag_id=tag_id
                    )
                )

        await self.session.flush()
        await self.session.refresh(transaction)
        return transaction

    async def create_transfer(
        self,
        *,
        source_account_id: int,
        destination_account_id: int,
        amount,
        transaction_date: datetime,
        description: str,
        notes: str | None = None,
        tags: Sequence[str] | None = None,
    ) -> tuple[Transaction, Transaction]:
        minor = to_minor_units(amount)
        validate_positive(minor, "amount")

        source = await self.accounts.get(source_account_id)
        destination = await self.accounts.get(destination_account_id)
        if source is None:
            raise MoneyError(f"source account {source_account_id} does not exist")
        if destination is None:
            raise MoneyError(f"destination account {destination_account_id} does not exist")
        if source_account_id == destination_account_id:
            raise MoneyError("source and destination accounts must differ")
        if source.type != "credit" and source.current_balance - minor < 0:
            raise MoneyError("insufficient funds in source account")

        # Atomic transfer: two linked transactions in one transaction.
        expense = Transaction(
            account_id=source_account_id,
            category_id=None,
            amount=minor,
            transaction_date=transaction_date,
            type="transfer",
            description=description,
            notes=notes,
            tags=",".join(self._parse_tags(tags)) if tags else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            linked_transaction_id=None,
        )
        income = Transaction(
            account_id=destination_account_id,
            category_id=None,
            amount=minor,
            transaction_date=transaction_date,
            type="transfer",
            description=description,
            notes=notes,
            tags=",".join(self._parse_tags(tags)) if tags else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            linked_transaction_id=None,
        )
        self.session.add(expense)
        self.session.add(income)
        await self.session.flush()  # get ids

        expense.linked_transaction_id = income.id
        income.linked_transaction_id = expense.id

        source.current_balance -= minor
        destination.current_balance += minor
        self.session.add(source)
        self.session.add(destination)

        tag_names = self._parse_tags(tags)
        if tag_names:
            tag_ids = await self._resolve_tag_ids(tag_names)
            for tag_id in tag_ids:
                self.session.add(
                    __import__("app.models.tag", fromlist=["TransactionTag"]).TransactionTag(
                        transaction_id=expense.id, tag_id=tag_id
                    )
                )
                self.session.add(
                    __import__("app.models.tag", fromlist=["TransactionTag"]).TransactionTag(
                        transaction_id=income.id, tag_id=tag_id
                    )
                )

        await self.session.flush()
        await self.session.refresh(expense)
        await self.session.refresh(income)
        return expense, income

    async def update(self, transaction_id: int, **fields) -> Transaction | None:
        # Rebalance is complex; for edits we reject balance-impacting changes
        # and support description/notes/date/category/tags edits only.
        transaction = await self.transactions.get(transaction_id)
        if transaction is None:
            return None
        allowed = {"description", "notes", "transaction_date", "category_id", "tags"}
        update_fields = {}
        for key, value in fields.items():
            if key in allowed:
                update_fields[key] = value
        if "tags" in update_fields:
            update_fields["tags"] = (
                ",".join(self._parse_tags(update_fields["tags"])) if update_fields["tags"] else None
            )
        update_fields["updated_at"] = datetime.utcnow()
        return await self.transactions.update(transaction_id, **update_fields)

    async def delete(self, transaction_id: int) -> bool:
        transaction = await self.transactions.get(transaction_id)
        if transaction is None:
            return False
        # Reverse balance effect before deleting.
        account = await self.accounts.get(transaction.account_id)
        if account is not None:
            if transaction.type == "income":
                account.current_balance -= transaction.amount
            elif transaction.type == "expense":
                account.current_balance += transaction.amount
            # transfers are handled by deleting both legs
            self.session.add(account)
        # If transfer, delete the linked leg too.
        if transaction.type == "transfer" and transaction.linked_transaction_id:
            linked = await self.transactions.get(transaction.linked_transaction_id)
            if linked is not None:
                linked_account = await self.accounts.get(linked.account_id)
                if linked_account is not None:
                    if linked.type == "income":
                        linked_account.current_balance -= linked.amount
                    elif linked.type == "expense":
                        linked_account.current_balance += linked.amount
                    self.session.add(linked_account)
                await self.transactions.delete(linked.id)
        await self.transactions.delete(transaction.id)
        await self.session.flush()
        return True

    async def list(self, **kwargs) -> tuple[Sequence[Transaction], int]:
        return await self.transactions.list(**kwargs)

    async def get(self, transaction_id: int) -> Transaction | None:
        return await self.transactions.get(transaction_id)
