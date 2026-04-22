"""
orders.py — Order placement functions for Binance Futures Testnet.

Each function:
  1. Validates its inputs via validators.py
  2. Delegates the signed HTTP request to BinanceClient
  3. Returns a typed OrderResult dataclass

No rich/CLI output lives here — that belongs in cli.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from loguru import logger

from .client import BinanceClient
from .validators import (
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)

ORDER_ENDPOINT = "/fapi/v1/order"


@dataclass
class OrderResult:
    """Typed representation of a Binance order response."""
    orderId: str
    symbol: str
    status: str
    executedQty: str
    avgPrice: str
    type: str

    @classmethod
    def from_response(cls, data: dict) -> "OrderResult":
        return cls(
            orderId=str(data.get("orderId", "N/A")),
            symbol=str(data.get("symbol", "N/A")),
            status=str(data.get("status", "N/A")),
            executedQty=str(data.get("executedQty", "0")),
            avgPrice=str(data.get("avgPrice", "0")),
            type=str(data.get("type", "N/A")),
        )


def place_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: float,
) -> OrderResult:
    """Place a MARKET order on Binance Futures Testnet."""
    sym = validate_symbol(symbol)
    sid = validate_side(side)
    qty = validate_quantity(quantity)

    params = {
        "symbol": sym,
        "side": sid,
        "type": "MARKET",
        "quantity": qty,
    }
    logger.info("Placing MARKET order | symbol={} side={} qty={}", sym, sid, qty)
    result = OrderResult.from_response(client.post(ORDER_ENDPOINT, params))
    logger.info("MARKET order accepted | orderId={} status={}", result.orderId, result.status)
    return result


def place_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    time_in_force: str = "GTC",
) -> OrderResult:
    """Place a LIMIT order on Binance Futures Testnet."""
    sym = validate_symbol(symbol)
    sid = validate_side(side)
    qty = validate_quantity(quantity)
    prc = validate_price(price, "LIMIT")

    params = {
        "symbol": sym,
        "side": sid,
        "type": "LIMIT",
        "quantity": qty,
        "price": prc,
        "timeInForce": time_in_force.upper(),
    }
    logger.info(
        "Placing LIMIT order | symbol={} side={} qty={} price={} tif={}",
        sym, sid, qty, prc, time_in_force,
    )
    result = OrderResult.from_response(client.post(ORDER_ENDPOINT, params))
    logger.info("LIMIT order accepted | orderId={} status={}", result.orderId, result.status)
    return result


def place_stop_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    stop_price: float,
    time_in_force: str = "GTC",
) -> OrderResult:
    """Place a STOP (stop-limit) order on Binance Futures Testnet."""
    sym = validate_symbol(symbol)
    sid = validate_side(side)
    qty = validate_quantity(quantity)
    prc = validate_price(price, "STOP_LIMIT")
    stp = validate_stop_price(stop_price, "STOP_LIMIT")

    params = {
        "symbol": sym,
        "side": sid,
        "type": "STOP",           # Binance Futures uses "STOP" for stop-limit orders
        "quantity": qty,
        "price": prc,
        "stopPrice": stp,
        "timeInForce": time_in_force.upper(),
    }
    logger.info(
        "Placing STOP_LIMIT order | symbol={} side={} qty={} price={} stopPrice={} tif={}",
        sym, sid, qty, prc, stp, time_in_force,
    )
    result = OrderResult.from_response(client.post(ORDER_ENDPOINT, params))
    logger.info(
        "STOP_LIMIT order accepted | orderId={} status={}",
        result.orderId, result.status,
    )
    return result
