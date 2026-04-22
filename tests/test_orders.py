"""
tests/test_orders.py — Unit tests for order placement functions.

BinanceClient is mocked — no real HTTP calls, no credentials required.
"""
import pytest
from unittest.mock import MagicMock, patch

from bot.exceptions import BinanceAPIError
from bot.orders import OrderResult, place_limit_order, place_market_order, place_stop_limit_order


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_MARKET_RESPONSE = {
    "orderId": 123456789,
    "symbol": "BTCUSDT",
    "status": "FILLED",
    "executedQty": "0.001",
    "avgPrice": "67000.00",
    "type": "MARKET",
}

MOCK_LIMIT_RESPONSE = {
    "orderId": 987654321,
    "symbol": "ETHUSDT",
    "status": "NEW",
    "executedQty": "0",
    "avgPrice": "0",
    "type": "LIMIT",
}

MOCK_STOP_RESPONSE = {
    "orderId": 111222333,
    "symbol": "BTCUSDT",
    "status": "NEW",
    "executedQty": "0",
    "avgPrice": "0",
    "type": "STOP",
}


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.dry_run = False
    return client


# ---------------------------------------------------------------------------
# OrderResult.from_response
# ---------------------------------------------------------------------------

class TestOrderResult:
    def test_from_response_maps_all_fields(self):
        result = OrderResult.from_response(MOCK_MARKET_RESPONSE)
        assert result.orderId == "123456789"
        assert result.symbol == "BTCUSDT"
        assert result.status == "FILLED"
        assert result.executedQty == "0.001"
        assert result.avgPrice == "67000.00"
        assert result.type == "MARKET"

    def test_from_response_handles_missing_fields(self):
        result = OrderResult.from_response({})
        assert result.orderId == "N/A"
        assert result.avgPrice == "0"

    def test_from_response_casts_order_id_to_string(self):
        result = OrderResult.from_response({"orderId": 999})
        assert result.orderId == "999"


# ---------------------------------------------------------------------------
# place_market_order
# ---------------------------------------------------------------------------

class TestPlaceMarketOrder:
    def test_returns_order_result(self, mock_client):
        mock_client.post.return_value = MOCK_MARKET_RESPONSE
        result = place_market_order(mock_client, "BTCUSDT", "BUY", 0.001)
        assert isinstance(result, OrderResult)
        assert result.status == "FILLED"

    def test_sends_correct_params(self, mock_client):
        mock_client.post.return_value = MOCK_MARKET_RESPONSE
        place_market_order(mock_client, "BTCUSDT", "BUY", 0.001)
        _, params = mock_client.post.call_args[0]
        assert params == {"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "quantity": 0.001}

    def test_normalises_symbol_to_uppercase(self, mock_client):
        mock_client.post.return_value = MOCK_MARKET_RESPONSE
        place_market_order(mock_client, "btcusdt", "buy", 0.001)
        _, params = mock_client.post.call_args[0]
        assert params["symbol"] == "BTCUSDT"
        assert params["side"] == "BUY"

    def test_invalid_symbol_raises_before_api_call(self, mock_client):
        with pytest.raises(ValueError, match="USDT or BUSD"):
            place_market_order(mock_client, "BTCETH", "BUY", 0.001)
        mock_client.post.assert_not_called()

    def test_invalid_side_raises_before_api_call(self, mock_client):
        with pytest.raises(ValueError, match="BUY or SELL"):
            place_market_order(mock_client, "BTCUSDT", "LONG", 0.001)
        mock_client.post.assert_not_called()

    def test_zero_quantity_raises_before_api_call(self, mock_client):
        with pytest.raises(ValueError, match="positive"):
            place_market_order(mock_client, "BTCUSDT", "BUY", 0)
        mock_client.post.assert_not_called()

    def test_api_error_propagates(self, mock_client):
        mock_client.post.side_effect = BinanceAPIError(400, -1121, "Invalid symbol.")
        with pytest.raises(BinanceAPIError):
            place_market_order(mock_client, "BTCUSDT", "BUY", 0.001)


# ---------------------------------------------------------------------------
# place_limit_order
# ---------------------------------------------------------------------------

class TestPlaceLimitOrder:
    def test_returns_order_result(self, mock_client):
        mock_client.post.return_value = MOCK_LIMIT_RESPONSE
        result = place_limit_order(mock_client, "ETHUSDT", "SELL", 1.0, 3000.0)
        assert result.type == "LIMIT"
        assert result.status == "NEW"

    def test_sends_correct_params(self, mock_client):
        mock_client.post.return_value = MOCK_LIMIT_RESPONSE
        place_limit_order(mock_client, "ETHUSDT", "BUY", 0.5, 3000.0, "IOC")
        _, params = mock_client.post.call_args[0]
        assert params["type"] == "LIMIT"
        assert params["price"] == 3000.0
        assert params["timeInForce"] == "IOC"
        assert params["quantity"] == 0.5

    def test_default_tif_is_gtc(self, mock_client):
        mock_client.post.return_value = MOCK_LIMIT_RESPONSE
        place_limit_order(mock_client, "ETHUSDT", "BUY", 0.5, 3000.0)
        _, params = mock_client.post.call_args[0]
        assert params["timeInForce"] == "GTC"

    def test_none_price_raises(self, mock_client):
        with pytest.raises((ValueError, TypeError)):
            place_limit_order(mock_client, "BTCUSDT", "BUY", 0.001, None)
        mock_client.post.assert_not_called()

    def test_negative_price_raises(self, mock_client):
        with pytest.raises(ValueError, match="positive"):
            place_limit_order(mock_client, "BTCUSDT", "BUY", 0.001, -500)
        mock_client.post.assert_not_called()


# ---------------------------------------------------------------------------
# place_stop_limit_order
# ---------------------------------------------------------------------------

class TestPlaceStopLimitOrder:
    def test_returns_order_result(self, mock_client):
        mock_client.post.return_value = MOCK_STOP_RESPONSE
        result = place_stop_limit_order(mock_client, "BTCUSDT", "SELL", 0.001, 45000, 44500)
        assert result.type == "STOP"

    def test_sends_correct_params(self, mock_client):
        mock_client.post.return_value = MOCK_STOP_RESPONSE
        place_stop_limit_order(mock_client, "BTCUSDT", "BUY", 0.001, 45000, 44500)
        _, params = mock_client.post.call_args[0]
        assert params["type"] == "STOP"
        assert params["price"] == 45000.0
        assert params["stopPrice"] == 44500.0
        assert params["timeInForce"] == "GTC"

    def test_missing_stop_price_raises(self, mock_client):
        with pytest.raises(ValueError, match="required"):
            place_stop_limit_order(mock_client, "BTCUSDT", "BUY", 0.001, 45000, None)
        mock_client.post.assert_not_called()

    def test_zero_stop_price_raises(self, mock_client):
        with pytest.raises(ValueError, match="positive"):
            place_stop_limit_order(mock_client, "BTCUSDT", "BUY", 0.001, 45000, 0)
        mock_client.post.assert_not_called()
