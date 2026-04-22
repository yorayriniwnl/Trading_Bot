from decimal import Decimal
from unittest.mock import patch

import pytest

from bot.exchange_info import SymbolRules, get_symbol_rules, validate_exchange_rules


SAMPLE_EXCHANGE_INFO = {
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "pricePrecision": 2,
            "quantityPrecision": 4,
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "261.10",
                    "maxPrice": "809484",
                    "tickSize": "0.10",
                },
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.0001",
                    "maxQty": "1000",
                    "stepSize": "0.0001",
                },
                {
                    "filterType": "MARKET_LOT_SIZE",
                    "minQty": "0.0001",
                    "maxQty": "120",
                    "stepSize": "0.0001",
                },
                {
                    "filterType": "MIN_NOTIONAL",
                    "notional": "100",
                },
            ],
        }
    ]
}


@pytest.fixture(autouse=True)
def clear_cache():
    from bot.exchange_info import clear_exchange_info_cache

    clear_exchange_info_cache()
    yield
    clear_exchange_info_cache()


def test_get_symbol_rules_builds_rules_from_payload():
    with patch(
        "bot.exchange_info._exchange_info_payload",
        return_value=SAMPLE_EXCHANGE_INFO,
    ):
        rules = get_symbol_rules("btcusdt")

    assert isinstance(rules, SymbolRules)
    assert rules.symbol == "BTCUSDT"
    assert rules.tick_size == Decimal("0.10")
    assert rules.lot_step_size == Decimal("0.0001")
    assert rules.market_max_qty == Decimal("120")
    assert rules.min_notional == Decimal("100")


def test_get_symbol_rules_raises_for_unknown_symbol():
    with patch(
        "bot.exchange_info._exchange_info_payload",
        return_value=SAMPLE_EXCHANGE_INFO,
    ):
        with pytest.raises(ValueError, match="not found"):
            get_symbol_rules("ETHUSDT")


def test_validate_exchange_rules_accepts_valid_limit_order():
    rules = SymbolRules(
        symbol="BTCUSDT",
        price_precision=2,
        quantity_precision=4,
        min_price=Decimal("261.10"),
        max_price=Decimal("809484"),
        tick_size=Decimal("0.10"),
        lot_min_qty=Decimal("0.0001"),
        lot_max_qty=Decimal("1000"),
        lot_step_size=Decimal("0.0001"),
        market_min_qty=Decimal("0.0001"),
        market_max_qty=Decimal("120"),
        market_step_size=Decimal("0.0001"),
        min_notional=Decimal("100"),
    )

    with patch("bot.exchange_info.get_symbol_rules", return_value=rules):
        validate_exchange_rules(
            symbol="BTCUSDT",
            order_type="LIMIT",
            quantity=0.002,
            price=60000.0,
        )


def test_validate_exchange_rules_rejects_invalid_price_tick():
    rules = SymbolRules(
        symbol="BTCUSDT",
        price_precision=2,
        quantity_precision=4,
        min_price=Decimal("261.10"),
        max_price=Decimal("809484"),
        tick_size=Decimal("0.10"),
        lot_min_qty=Decimal("0.0001"),
        lot_max_qty=Decimal("1000"),
        lot_step_size=Decimal("0.0001"),
        market_min_qty=Decimal("0.0001"),
        market_max_qty=Decimal("120"),
        market_step_size=Decimal("0.0001"),
        min_notional=Decimal("100"),
    )

    with patch("bot.exchange_info.get_symbol_rules", return_value=rules):
        with pytest.raises(ValueError, match="tick size"):
            validate_exchange_rules(
                symbol="BTCUSDT",
                order_type="LIMIT",
                quantity=0.002,
                price=60000.05,
            )


def test_validate_exchange_rules_rejects_invalid_quantity_step():
    rules = SymbolRules(
        symbol="BTCUSDT",
        price_precision=2,
        quantity_precision=4,
        min_price=Decimal("261.10"),
        max_price=Decimal("809484"),
        tick_size=Decimal("0.10"),
        lot_min_qty=Decimal("0.0001"),
        lot_max_qty=Decimal("1000"),
        lot_step_size=Decimal("0.0001"),
        market_min_qty=Decimal("0.0001"),
        market_max_qty=Decimal("120"),
        market_step_size=Decimal("0.0001"),
        min_notional=Decimal("100"),
    )

    with patch("bot.exchange_info.get_symbol_rules", return_value=rules):
        with pytest.raises(ValueError, match="step size"):
            validate_exchange_rules(
                symbol="BTCUSDT",
                order_type="MARKET",
                quantity=0.00015,
            )


def test_validate_exchange_rules_skips_when_metadata_is_unavailable():
    with patch("bot.exchange_info.get_symbol_rules", return_value=None):
        validate_exchange_rules(
            symbol="BTCUSDT",
            order_type="MARKET",
            quantity=0.001,
        )
