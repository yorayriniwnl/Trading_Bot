"""
Shared order preparation and execution helpers.

This module keeps the CLI and the web UI on the same order-submission path.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .client import BinanceClient
from .exchange_info import validate_exchange_rules
from .orders import OrderResult, place_limit_order, place_market_order, place_stop_limit_order
from .validators import (
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
    validate_time_in_force,
)


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"
    dry_run: bool = False


def prepare_order_request(
    *,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
    time_in_force: str = "GTC",
    dry_run: bool = False,
    validate_exchange_metadata: bool = False,
) -> OrderRequest:
    """Validate and normalise user input into a reusable order request."""
    ot = validate_order_type(order_type)
    request = OrderRequest(
        symbol=validate_symbol(symbol),
        side=validate_side(side),
        order_type=ot,
        quantity=validate_quantity(quantity),
        price=validate_price(price, ot) if ot != "MARKET" else None,
        stop_price=validate_stop_price(stop_price, ot),
        time_in_force=validate_time_in_force(time_in_force) if ot != "MARKET" else "GTC",
        dry_run=bool(dry_run),
    )
    if validate_exchange_metadata:
        validate_exchange_rules(
            symbol=request.symbol,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price,
        )
    return request


def execute_order(request: OrderRequest) -> OrderResult:
    """Submit a validated order request using the Binance client."""
    with BinanceClient(dry_run=request.dry_run) as client:
        if request.order_type == "MARKET":
            return place_market_order(client, request.symbol, request.side, request.quantity)
        if request.order_type == "LIMIT":
            return place_limit_order(
                client,
                request.symbol,
                request.side,
                request.quantity,
                request.price,
                request.time_in_force,
            )
        return place_stop_limit_order(
            client,
            request.symbol,
            request.side,
            request.quantity,
            request.price,
            request.stop_price,
            request.time_in_force,
        )


def submit_order(
    *,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
    time_in_force: str = "GTC",
    dry_run: bool = False,
    validate_exchange_metadata: bool = False,
) -> tuple[OrderRequest, OrderResult]:
    """Prepare and submit an order in one call."""
    request = prepare_order_request(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        time_in_force=time_in_force,
        dry_run=dry_run,
        validate_exchange_metadata=validate_exchange_metadata,
    )
    return request, execute_order(request)
