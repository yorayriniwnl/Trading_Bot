"""
Pure validation helpers with no side effects.

All functions raise ValueError with descriptive messages on invalid input.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT"}
VALID_TIME_IN_FORCE = {"FOK", "GTC", "IOC"}
SYMBOL_BODY_PATTERN = re.compile(r"^[A-Z0-9]+$")
QUOTE_SUFFIXES = ("USDT", "BUSD")


def _parse_positive_number(value: float | str, field_name: str) -> float:
    try:
        parsed = Decimal(str(value).strip())
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number, got '{value}'.")

    if not parsed.is_finite():
        raise ValueError(f"{field_name} must be a finite number, got '{value}'.")
    if parsed <= 0:
        raise ValueError(f"{field_name} must be positive, got {parsed}.")
    return float(parsed)


def validate_symbol(symbol: str) -> str:
    """Return a normalised symbol or raise ValueError."""
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("Symbol must be a non-empty string.")

    normalised = symbol.strip().upper()
    suffix = next((quote for quote in QUOTE_SUFFIXES if normalised.endswith(quote)), None)
    body = normalised[: -len(suffix)] if suffix else ""

    if (
        suffix is None
        or not 2 <= len(body) <= 20
        or not SYMBOL_BODY_PATTERN.fullmatch(body)
        or not any(char.isalpha() for char in body)
    ):
        raise ValueError(
            f"Invalid symbol '{normalised}'. "
            "Expected an uppercase alphanumeric base asset ending in USDT or BUSD "
            "(e.g. BTCUSDT or 1000SHIBUSDT)."
        )
    return normalised


def validate_side(side: str) -> str:
    """Return a normalised side ('BUY' or 'SELL') or raise ValueError."""
    if not isinstance(side, str) or not side.strip():
        raise ValueError("Side must be a non-empty string.")
    normalised = side.strip().upper()
    if normalised not in VALID_SIDES:
        raise ValueError(f"Invalid side '{normalised}'. Must be BUY or SELL.")
    return normalised


def validate_quantity(quantity: float | str) -> float:
    """Return a validated quantity (positive finite float, max 8 dp)."""
    qty = _parse_positive_number(quantity, "Quantity")

    normalised = Decimal(str(quantity).strip())
    if normalised.as_tuple().exponent < -8:
        raise ValueError(
            f"Quantity exceeds 8 decimal places: {quantity}. "
            "Binance rejects sub-satoshi precision."
        )
    return round(qty, 8)


def validate_price(price: float | str | None, order_type: str) -> float | None:
    """
    Validate price according to order-type rules.

    MARKET orders ignore price. LIMIT and STOP_LIMIT orders require a positive,
    finite number.
    """
    ot = order_type.strip().upper()
    if ot not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Unknown order type '{ot}'. Valid types: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )

    if ot == "MARKET":
        return None
    if price is None:
        raise ValueError(f"Price is required for {ot} orders.")
    return _parse_positive_number(price, "Price")


def validate_stop_price(stop_price: float | str | None, order_type: str) -> float | None:
    """Stop price is required only for STOP_LIMIT orders."""
    ot = order_type.strip().upper()
    if ot != "STOP_LIMIT":
        return None
    if stop_price is None:
        raise ValueError("stop_price is required for STOP_LIMIT orders.")
    return _parse_positive_number(stop_price, "stop_price")


def validate_order_type(order_type: str) -> str:
    """Return a normalised order type or raise ValueError."""
    if not isinstance(order_type, str) or not order_type.strip():
        raise ValueError("order_type must be a non-empty string.")
    normalised = order_type.strip().upper()
    if normalised not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{normalised}'. "
            f"Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return normalised


def validate_time_in_force(time_in_force: str | None) -> str:
    """Return a normalised time-in-force or raise ValueError."""
    tif = (time_in_force or "GTC").strip().upper()
    if tif not in VALID_TIME_IN_FORCE:
        raise ValueError(
            f"Invalid time-in-force '{tif}'. Must be one of: "
            f"{', '.join(sorted(VALID_TIME_IN_FORCE))}."
        )
    return tif
