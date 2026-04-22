"""
tests/test_validators.py — Unit tests for the validators module.
Run with: pytest tests/ -v
"""
import pytest
from bot.validators import (
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)


# ── validate_symbol ─────────────────────────────────────────────────────────

class TestValidateSymbol:
    def test_valid_usdt_pair(self):
        assert validate_symbol("btcusdt") == "BTCUSDT"

    def test_valid_busd_pair(self):
        assert validate_symbol("ethbusd") == "ETHBUSD"

    def test_strips_whitespace(self):
        assert validate_symbol("  SOLUSDT  ") == "SOLUSDT"

    def test_invalid_no_suffix(self):
        with pytest.raises(ValueError, match="USDT or BUSD"):
            validate_symbol("BTCETH")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            validate_symbol("")

    def test_numeric_symbol(self):
        with pytest.raises(ValueError):
            validate_symbol("123USDT")


# ── validate_side ───────────────────────────────────────────────────────────

class TestValidateSide:
    def test_buy_lowercase(self):
        assert validate_side("buy") == "BUY"

    def test_sell_uppercase(self):
        assert validate_side("SELL") == "SELL"

    def test_invalid_side(self):
        with pytest.raises(ValueError, match="BUY or SELL"):
            validate_side("LONG")

    def test_empty_side(self):
        with pytest.raises(ValueError):
            validate_side("")


# ── validate_quantity ───────────────────────────────────────────────────────

class TestValidateQuantity:
    def test_valid_integer_quantity(self):
        assert validate_quantity(1) == 1.0

    def test_valid_decimal_quantity(self):
        assert validate_quantity("0.001") == 0.001

    def test_zero_raises(self):
        with pytest.raises(ValueError, match="positive"):
            validate_quantity(0)

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="positive"):
            validate_quantity(-5.0)

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="number"):
            validate_quantity("abc")

    def test_too_many_decimals(self):
        with pytest.raises(ValueError, match="8 decimal places"):
            validate_quantity(0.000000001)  # 9 dp


# ── validate_price ──────────────────────────────────────────────────────────

class TestValidatePrice:
    def test_market_ignores_price(self):
        assert validate_price(50000, "MARKET") is None

    def test_market_none_is_ok(self):
        assert validate_price(None, "MARKET") is None

    def test_limit_requires_price(self):
        with pytest.raises(ValueError, match="required"):
            validate_price(None, "LIMIT")

    def test_limit_positive_price(self):
        assert validate_price(50000.5, "LIMIT") == 50000.5

    def test_limit_negative_price(self):
        with pytest.raises(ValueError, match="positive"):
            validate_price(-1, "LIMIT")

    def test_invalid_order_type(self):
        with pytest.raises(ValueError, match="Unknown order type"):
            validate_price(100, "UNKNOWN")


# ── validate_stop_price ─────────────────────────────────────────────────────

class TestValidateStopPrice:
    def test_stop_limit_requires_stop_price(self):
        with pytest.raises(ValueError, match="required"):
            validate_stop_price(None, "STOP_LIMIT")

    def test_stop_limit_valid(self):
        assert validate_stop_price(44500.0, "STOP_LIMIT") == 44500.0

    def test_non_stop_limit_returns_none(self):
        assert validate_stop_price(44500.0, "LIMIT") is None
        assert validate_stop_price(44500.0, "MARKET") is None


# ── validate_order_type ─────────────────────────────────────────────────────

class TestValidateOrderType:
    def test_valid_types(self):
        for t in ("MARKET", "LIMIT", "STOP_LIMIT"):
            assert validate_order_type(t) == t

    def test_lowercase_normalised(self):
        assert validate_order_type("market") == "MARKET"

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="Invalid order type"):
            validate_order_type("ICEBERG")
