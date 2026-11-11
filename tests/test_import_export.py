"""CSV import and export tests."""

import pytest

from app.repositories.transaction_repository import TransactionRepository
from app.services.export_service import ExportService
from app.services.import_service import ImportService


def test_import_rejects_non_csv():
    svc = ImportService()
    with pytest.raises(ValueError):
        svc.validate_file("data.txt", b"a,b\n1,2")


def test_import_rejects_oversized():
    svc = ImportService(max_upload_bytes=10)
    with pytest.raises(ValueError):
        svc.validate_file("data.csv", b"x" * 100)


def test_import_parse_and_preview():
    svc = ImportService()
    content = b"date,description,amount\n2026-01-10,Groceries,10.50\n2026-01-11,Salary,100.00\n"
    columns, rows = svc.parse(content)
    assert columns == ["date", "description", "amount"]
    assert len(rows) == 2

    preview = svc.preview(
        columns,
        rows,
        mapping={
            "transaction_date": "date",
            "description": "description",
            "amount": "amount",
            "account_id": "",
        },
        existing_keys=set(),
    )
    assert preview.total == 2
    assert preview.valid_count == 2
    assert preview.error_count == 0


def test_import_detects_invalid_rows():
    svc = ImportService()
    content = b"date,description,amount\nnot-a-date,Groceries,10.50\n2026-01-11,,100.00\n"
    columns, rows = svc.parse(content)
    preview = svc.preview(
        columns,
        rows,
        mapping={
            "transaction_date": "date",
            "description": "description",
            "amount": "amount",
            "account_id": "",
        },
        existing_keys=set(),
    )
    assert preview.valid_count == 0
    assert preview.error_count == 2


def test_import_duplicate_detection():
    svc = ImportService()

    # build fake existing keys
    class FakeTx:
        def __init__(self, d, desc, amt):
            self.transaction_date = d
            self.description = desc
            self.amount = amt

    existing = {("groceries", "2026-01-10", 1050)}
    content = b"date,description,amount\n2026-01-10,Groceries,10.50\n"
    columns, rows = svc.parse(content)
    preview = svc.preview(
        columns,
        rows,
        mapping={
            "transaction_date": "date",
            "description": "description",
            "amount": "amount",
            "account_id": "",
        },
        existing_keys=existing,
    )
    assert preview.duplicate_count == 1
    assert preview.rows[0].valid is True  # duplicate is a warning, not error


async def test_export_roundtrip_values(session):
    repo = TransactionRepository(session)
    svc = ExportService(repo)
    filename, payload, ct = await svc.export()
    assert filename.endswith(".csv")
    assert "text/csv" in ct
    text = payload.decode("utf-8")
    assert "id,date,type,account_id" in text
    assert "amount_minor" in text
