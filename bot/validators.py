"""
validators.py — Pure validation functions with no side effects.
All functions raise ValueError with descriptive messages on bad input.
"""
from __future__ import annotations

import re

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT"}
SYMBOL_PATTERN = re.compile(r"^[A-Z]{2,10}(USDT|BUSD)$")


def validate_symbol(symbol: str) -> str:
    """Return normalised symbol or raise ValueError."""
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("Symbol must be a non-empty string.")
    normalised = symbol.strip().upper()
    if not SYMBOL_PATTERN.match(normalised):
        raise ValueError(
            f"Invalid symbol '{normalised}'. "
            "Expected uppercase letters ending in USDT or BUSD (e.g. BTCUSDT)."
        )
    return normalised


def validate_side(side: str) -> str:
    """Return normalised side ('BUY' | 'SELL') or raise ValueError."""
    if not isinstance(side, str) or not side.strip():
        raise ValueError("Side must be a non-empty string.")
    normalised = side.strip().upper()
    if normalised not in VALID_SIDES:
        raise ValueError(f"Invalid side '{normalised}'. Must be BUY or SELL.")
    return normalised


def validate_quantity(quantity: float | str) -> float:
    """Return validated quantity (positive float, ≤8 dp) or raise ValueError."""
    try:
        qty = float(quantity)
    except (TypeError, ValueError):
        raise ValueError(f"Quantity must be a number, got '{quantity}'.")
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}.")
    # Enforce max 8 decimal places
    rounded = round(qty, 8)
    if abs(rounded - qty) > 1e-12:
        raise ValueError(
            f"Quantity exceeds 8 decimal places: {quantity}. "
            "Binance rejects sub-satoshi precision."
        )
    return rounded


def validate_price(price: float | str | None, order_type: str) -> float | None:
    """
    Validate price according to order type rules:
    - MARKET: price must be None (ignored)
    - LIMIT / STOP_LIMIT: price must be a positive number
    Returns the validated price or None.
    """
    ot = order_type.strip().upper()
    if ot not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Unknown order type '{ot}'. Valid types: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )

    if ot == "MARKET":
        if price is not None:
            # Silently ignore, but callers should be aware
            return None
        return None

    # LIMIT or STOP_LIMIT — price is required
    if price is None:
        raise ValueError(f"Price is required for {ot} orders.")
    try:
        p = float(price)
    except (TypeError, ValueError):
        raise ValueError(f"Price must be a number, got '{price}'.")
    if p <= 0:
        raise ValueError(f"Price must be positive, got {p}.")
    return p


def validate_stop_price(stop_price: float | str | None, order_type: str) -> float | None:
    """Stop price is required only for STOP_LIMIT orders."""
    ot = order_type.strip().upper()
    if ot != "STOP_LIMIT":
        return None
    if stop_price is None:
        raise ValueError("stop_price is required for STOP_LIMIT orders.")
    try:
        sp = float(stop_price)
    except (TypeError, ValueError):
        raise ValueError(f"stop_price must be a number, got '{stop_price}'.")
    if sp <= 0:
        raise ValueError(f"stop_price must be positive, got {sp}.")
    return sp


def validate_order_type(order_type: str) -> str:
    """Return normalised order type or raise ValueError."""
    if not isinstance(order_type, str) or not order_type.strip():
        raise ValueError("order_type must be a non-empty string.")
    normalised = order_type.strip().upper()
    if normalised not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{normalised}'. "
            f"Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return normalised
