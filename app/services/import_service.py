"""CSV import service.

Parses transaction CSV files, supports column mapping, validation, duplicate
detection and staged import. Nothing is written to the database until the
caller confirms the import.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime

from app.services.currency import MoneyError, parse_amount

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

DATE_FORMATS = (
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%d.%m.%Y %H:%M",
)


@dataclass
class ImportRow:
    line_number: int
    raw: dict
    mapped: dict
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    valid: bool = False


@dataclass
class ImportPreview:
    columns: list[str]
    rows: list[ImportRow]
    total: int
    valid_count: int
    error_count: int
    duplicate_count: int


class ImportService:
    def __init__(self, max_upload_bytes: int = MAX_UPLOAD_BYTES):
        self.max_upload_bytes = max_upload_bytes

    def validate_file(self, filename: str, content: bytes) -> None:
        if not filename.lower().endswith(".csv"):
            raise ValueError("only CSV files are allowed")
        if len(content) > self.max_upload_bytes:
            raise ValueError(f"file too large (max {self.max_upload_bytes // 1024 // 1024} MB)")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content.decode("cp1251")
            except UnicodeDecodeError as exc:
                raise ValueError("file must be UTF-8 or Windows-1251 encoded") from exc

    def parse(self, content: bytes, encoding: str | None = None) -> tuple[list[str], list[dict]]:
        if encoding is None:
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("cp1251")
        else:
            text = content.decode(encoding)
        reader = csv.DictReader(io.StringIO(text))
        columns = reader.fieldnames or []
        rows = [dict(row) for row in reader]
        return columns, rows

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        value = value.strip()
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _detect_duplicates(existing_keys: set, mapped: dict) -> bool:
        date_val = mapped.get("transaction_date_parsed")
        key = (
            (mapped.get("description") or "").strip().lower(),
            date_val.date().isoformat() if date_val else "",
            mapped.get("amount_minor"),
        )
        return key in existing_keys

    def preview(
        self,
        columns: list[str],
        rows: list[dict],
        mapping: dict,
        existing_keys: set,
    ) -> ImportPreview:
        """Apply column mapping and validate each row without writing."""
        import_rows: list[ImportRow] = []
        valid = 0
        errors = 0
        dupes = 0

        for idx, raw in enumerate(rows, start=2):  # header is line 1
            mapped = {}
            for model_field, csv_col in mapping.items():
                if csv_col:
                    mapped[model_field] = (raw.get(csv_col) or "").strip()

            row = ImportRow(line_number=idx, raw=raw, mapped=mapped)

            # validate date
            date_val = self._parse_date(mapped.get("transaction_date"))
            if date_val is None:
                row.errors.append("invalid or missing date")
            else:
                mapped["transaction_date_parsed"] = date_val

            # validate amount
            try:
                amount_minor = parse_amount(mapped.get("amount", ""))
                if amount_minor <= 0:
                    row.errors.append("amount must be positive")
                else:
                    mapped["amount_minor"] = amount_minor
            except MoneyError as exc:
                row.errors.append(str(exc))

            # required fields
            if not mapped.get("description"):
                row.errors.append("description is required")

            if self._detect_duplicates(existing_keys, mapped):
                row.warnings.append("possible duplicate transaction")
                dupes += 1

            if row.errors:
                errors += 1
            else:
                valid += 1
                row.valid = True

            import_rows.append(row)

        return ImportPreview(
            columns=columns,
            rows=import_rows,
            total=len(rows),
            valid_count=valid,
            error_count=errors,
            duplicate_count=dupes,
        )

    @staticmethod
    def build_existing_keys(transactions) -> set:
        keys = set()
        for t in transactions:
            keys.add(
                (
                    (t.description or "").strip().lower(),
                    t.transaction_date.date().isoformat(),
                    t.amount,
                )
            )
        return keys
