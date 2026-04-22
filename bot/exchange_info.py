"""
Public exchange metadata helpers for Binance Futures Testnet.

This module performs optional preflight validation against Binance symbol
filters so the CLI and UI can catch common issues before sending an order.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any, Optional

import httpx
from loguru import logger

from .client import BASE_URL

EXCHANGE_INFO_ENDPOINT = "/fapi/v1/exchangeInfo"


@dataclass(frozen=True)
class SymbolRules:
    symbol: str
    price_precision: int
    quantity_precision: int
    min_price: Optional[Decimal]
    max_price: Optional[Decimal]
    tick_size: Optional[Decimal]
    lot_min_qty: Optional[Decimal]
    lot_max_qty: Optional[Decimal]
    lot_step_size: Optional[Decimal]
    market_min_qty: Optional[Decimal]
    market_max_qty: Optional[Decimal]
    market_step_size: Optional[Decimal]
    min_notional: Optional[Decimal]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SymbolRules":
        filters = {
            entry["filterType"]: entry
            for entry in payload.get("filters", [])
            if "filterType" in entry
        }
        price_filter = filters.get("PRICE_FILTER", {})
        lot_filter = filters.get("LOT_SIZE", {})
        market_lot_filter = filters.get("MARKET_LOT_SIZE", lot_filter)
        notional_filter = filters.get("MIN_NOTIONAL", {})
        min_notional = notional_filter.get("notional", notional_filter.get("minNotional"))

        return cls(
            symbol=str(payload["symbol"]),
            price_precision=int(payload.get("pricePrecision", 8)),
            quantity_precision=int(payload.get("quantityPrecision", 8)),
            min_price=_to_decimal(price_filter.get("minPrice")),
            max_price=_to_decimal(price_filter.get("maxPrice")),
            tick_size=_to_decimal(price_filter.get("tickSize")),
            lot_min_qty=_to_decimal(lot_filter.get("minQty")),
            lot_max_qty=_to_decimal(lot_filter.get("maxQty")),
            lot_step_size=_to_decimal(lot_filter.get("stepSize")),
            market_min_qty=_to_decimal(market_lot_filter.get("minQty")),
            market_max_qty=_to_decimal(market_lot_filter.get("maxQty")),
            market_step_size=_to_decimal(market_lot_filter.get("stepSize")),
            min_notional=_to_decimal(min_notional),
        )


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value in (None, "", "0", 0):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _is_multiple(value: Decimal, step: Decimal) -> bool:
    if step <= 0:
        return True
    return (value % step) == 0


@lru_cache(maxsize=1)
def _exchange_info_payload() -> dict[str, Any]:
    logger.debug("Fetching exchange metadata | endpoint={}", EXCHANGE_INFO_ENDPOINT)
    with httpx.Client(
        base_url=BASE_URL,
        timeout=httpx.Timeout(8.0, connect=3.0),
    ) as client:
        response = client.get(EXCHANGE_INFO_ENDPOINT)
        response.raise_for_status()
        data = response.json()
    logger.debug(
        "Fetched exchange metadata | symbols={}",
        len(data.get("symbols", [])),
    )
    return data


def clear_exchange_info_cache() -> None:
    _exchange_info_payload.cache_clear()


def get_symbol_rules(symbol: str) -> Optional[SymbolRules]:
    normalised_symbol = symbol.strip().upper()
    try:
        payload = _exchange_info_payload()
    except Exception as exc:
        logger.warning(
            "Skipping exchange-rule validation for {} because metadata could not be loaded: {}",
            normalised_symbol,
            exc,
        )
        return None

    for entry in payload.get("symbols", []):
        if entry.get("symbol") == normalised_symbol:
            return SymbolRules.from_payload(entry)

    raise ValueError(
        f"Symbol '{normalised_symbol}' was not found in Binance Futures Testnet exchange metadata."
    )


def validate_exchange_rules(
    *,
    symbol: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
) -> None:
    """
    Best-effort preflight validation against Binance symbol filters.

    If exchange metadata is unavailable, the function logs a warning and
    returns without blocking local validation.
    """
    rules = get_symbol_rules(symbol)
    if rules is None:
        return

    qty = Decimal(str(quantity))
    order_kind = order_type.strip().upper()

    if order_kind == "MARKET":
        _validate_quantity(
            field_name="quantity",
            value=qty,
            minimum=rules.market_min_qty or rules.lot_min_qty,
            maximum=rules.market_max_qty or rules.lot_max_qty,
            step=rules.market_step_size or rules.lot_step_size,
            symbol=rules.symbol,
        )
        return

    prc = Decimal(str(price))
    _validate_quantity(
        field_name="quantity",
        value=qty,
        minimum=rules.lot_min_qty,
        maximum=rules.lot_max_qty,
        step=rules.lot_step_size,
        symbol=rules.symbol,
    )
    _validate_price(
        field_name="price",
        value=prc,
        minimum=rules.min_price,
        maximum=rules.max_price,
        tick_size=rules.tick_size,
        symbol=rules.symbol,
    )

    if rules.min_notional is not None and (qty * prc) < rules.min_notional:
        raise ValueError(
            f"Order notional must be at least {_format_decimal(rules.min_notional)} "
            f"for {rules.symbol}. Current notional: {_format_decimal(qty * prc)}."
        )

    if order_kind == "STOP_LIMIT" and stop_price is not None:
        _validate_price(
            field_name="stop_price",
            value=Decimal(str(stop_price)),
            minimum=rules.min_price,
            maximum=rules.max_price,
            tick_size=rules.tick_size,
            symbol=rules.symbol,
        )


def _validate_quantity(
    *,
    field_name: str,
    value: Decimal,
    minimum: Optional[Decimal],
    maximum: Optional[Decimal],
    step: Optional[Decimal],
    symbol: str,
) -> None:
    if minimum is not None and value < minimum:
        raise ValueError(
            f"{field_name} must be at least {_format_decimal(minimum)} for {symbol}."
        )
    if maximum is not None and value > maximum:
        raise ValueError(
            f"{field_name} must be no more than {_format_decimal(maximum)} for {symbol}."
        )
    if step is not None and not _is_multiple(value, step):
        raise ValueError(
            f"{field_name} must align with step size {_format_decimal(step)} for {symbol}."
        )


def _validate_price(
    *,
    field_name: str,
    value: Decimal,
    minimum: Optional[Decimal],
    maximum: Optional[Decimal],
    tick_size: Optional[Decimal],
    symbol: str,
) -> None:
    if minimum is not None and value < minimum:
        raise ValueError(
            f"{field_name} must be at least {_format_decimal(minimum)} for {symbol}."
        )
    if maximum is not None and value > maximum:
        raise ValueError(
            f"{field_name} must be no more than {_format_decimal(maximum)} for {symbol}."
        )
    if tick_size is not None and not _is_multiple(value, tick_size):
        raise ValueError(
            f"{field_name} must align with tick size {_format_decimal(tick_size)} for {symbol}."
        )
