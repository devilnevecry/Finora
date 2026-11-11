"""Financial correctness tests — money arithmetic and rounding."""

from decimal import Decimal

import pytest

from app.services.currency import (
    MoneyError,
    from_minor_units,
    parse_amount,
    to_minor_units,
    validate_non_negative,
    validate_positive,
)


def test_to_minor_units_basic():
    assert to_minor_units("10.00") == 1000
    assert to_minor_units(10) == 1000
    assert to_minor_units(Decimal("10.50")) == 1050


def test_to_minor_units_round_half_up():
    assert to_minor_units("10.005") == 1001  # half up
    assert to_minor_units("10.004") == 1000
    assert to_minor_units("0.009") == 1


def test_from_minor_units():
    assert from_minor_units(1050) == Decimal("10.50")
    assert from_minor_units(1000) == Decimal("10.00")


def test_parse_amount_symbols_and_separators():
    assert parse_amount("$1,234.56") == 123456
    assert parse_amount("1234.56") == 123456
    assert parse_amount("10") == 1000


def test_validate_positive_rejects_zero_and_negative():
    with pytest.raises(MoneyError):
        validate_positive(0)
    with pytest.raises(MoneyError):
        validate_positive(-5)
    validate_positive(1)


def test_validate_non_negative_allows_zero():
    validate_non_negative(0)
    validate_non_negative(100)
    with pytest.raises(MoneyError):
        validate_non_negative(-1)


def test_to_minor_units_rejects_bool():
    with pytest.raises(MoneyError):
        to_minor_units(True)
