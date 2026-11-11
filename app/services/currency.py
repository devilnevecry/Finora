"""Currency and money handling.

All financial amounts are stored as integer minor currency units (cents) to
avoid binary floating-point arithmetic. This module provides conversion
between human-readable decimal strings and minor units with explicit rounding
rules (ROUND_HALF_UP).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MINOR_UNITS = 100  # cents per base currency unit


class MoneyError(ValueError):
    """Raised for invalid monetary input."""


def to_minor_units(amount) -> int:
    """Convert an amount (Decimal, int, float, or str) to integer minor units.

    Rounding rule: ROUND_HALF_UP at the minor-unit scale.
    """
    if isinstance(amount, bool):
        raise MoneyError("amount must not be a boolean")
    try:
        decimal = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MoneyError(f"invalid amount: {amount!r}") from exc
    if decimal.is_nan() or decimal.is_infinite():
        raise MoneyError("amount must be a finite number")
    minor = (decimal * MINOR_UNITS).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(minor)


def from_minor_units(minor_units: int) -> Decimal:
    """Convert integer minor units to a Decimal in base currency units."""
    return Decimal(int(minor_units)) / Decimal(MINOR_UNITS)


def format_amount(minor_units: int, symbol: str = "$") -> str:
    """Format minor units as a localized-looking currency string (English)."""
    units = Decimal(int(minor_units)) / Decimal(MINOR_UNITS)
    sign = "-" if units < 0 else ""
    abs_units = abs(units)
    return f"{sign}{symbol}{abs_units:.2f}"


def parse_amount(text: str) -> int:
    """Parse a user-supplied amount string into minor units.

    Accepts an optional leading currency symbol and thousands separators.
    """
    if text is None:
        raise MoneyError("amount is required")
    cleaned = str(text).strip()
    for ch in ("$", "€", "£", "₽", " ", ","):
        cleaned = cleaned.replace(ch, "")
    if cleaned == "":
        raise MoneyError("amount is required")
    return to_minor_units(cleaned)


def validate_positive(minor_units: int, field: str = "amount") -> None:
    if minor_units <= 0:
        raise MoneyError(f"{field} must be positive")


def validate_non_negative(minor_units: int, field: str = "amount") -> None:
    if minor_units < 0:
        raise MoneyError(f"{field} must not be negative")


__all__ = [
    "MoneyError",
    "to_minor_units",
    "from_minor_units",
    "format_amount",
    "parse_amount",
    "validate_positive",
    "validate_non_negative",
    "MINOR_UNITS",
]
