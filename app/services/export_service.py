"""CSV export service.

Exports transactions to CSV with optional date range, account, type and
category filters. Values are written as minor units with a separate
human-readable column. UTF-8 encoded.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from app.repositories.transaction_repository import TransactionRepository


class ExportService:
    def __init__(self, transaction_repository: TransactionRepository):
        self.transactions = transaction_repository

    async def export(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        account_id: int | None = None,
        type: str | None = None,
        category_id: int | None = None,
    ) -> tuple[str, bytes, str]:
        transactions, _ = await self.transactions.list(
            account_id=account_id,
            category_id=category_id,
            type=type,
            date_from=date_from,
            date_to=date_to,
            sort_by="transaction_date",
            sort_dir="asc",
            limit=100000,
            offset=0,
        )

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(
            [
                "id",
                "date",
                "type",
                "account_id",
                "category_id",
                "description",
                "notes",
                "tags",
                "amount_minor",
                "amount",
            ]
        )
        for t in transactions:
            units = t.amount / 100
            writer.writerow(
                [
                    t.id,
                    t.transaction_date.strftime("%Y-%m-%d %H:%M:%S"),
                    t.type,
                    t.account_id,
                    t.category_id or "",
                    t.description,
                    t.notes or "",
                    t.tags or "",
                    t.amount,
                    f"{units:.2f}",
                ]
            )

        payload = output.getvalue().encode("utf-8")
        filename = f"finora_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        return filename, payload, "text/csv; charset=utf-8"
