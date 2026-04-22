"""
tests/test_client.py — Unit tests for BinanceClient.

httpx.Client is patched so no real network calls are made.
Environment variables are injected via monkeypatch.
"""
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest

from bot.exceptions import BinanceAPIError, BinanceNetworkError, BinanceTimeoutError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
    """Inject dummy credentials so BinanceClient.__init__ doesn't raise."""
    monkeypatch.setenv("BINANCE_TESTNET_API_KEY", "test_api_key_123")
    monkeypatch.setenv("BINANCE_TESTNET_SECRET", "test_secret_abc")


def _make_mock_response(body: dict, status_code: int = 200):
    """Build a minimal fake httpx.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.is_success = (200 <= status_code < 300)
    mock.json.return_value = body
    mock.text = json.dumps(body)
    return mock


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestBinanceClientInit:
    def test_raises_if_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("BINANCE_TESTNET_API_KEY", raising=False)
        from bot.client import BinanceClient
        with pytest.raises(EnvironmentError, match="BINANCE_TESTNET_API_KEY"):
            BinanceClient()

    def test_raises_if_secret_missing(self, monkeypatch):
        monkeypatch.delenv("BINANCE_TESTNET_SECRET", raising=False)
        from bot.client import BinanceClient
        with pytest.raises(EnvironmentError, match="BINANCE_TESTNET_SECRET"):
            BinanceClient()

    def test_dry_run_skips_http_client(self):
        from bot.client import BinanceClient
        client = BinanceClient(dry_run=True)
        assert client.dry_run is True
        assert not hasattr(client, "_http")

    def test_dry_run_does_not_require_credentials(self, monkeypatch):
        monkeypatch.delenv("BINANCE_TESTNET_API_KEY", raising=False)
        monkeypatch.delenv("BINANCE_TESTNET_SECRET", raising=False)

        from bot.client import BinanceClient

        client = BinanceClient(dry_run=True)
        assert client.dry_run is True


# ---------------------------------------------------------------------------
# Request signing
# ---------------------------------------------------------------------------

class TestSigning:
    def test_signature_is_valid_hmac(self):
        from bot.client import BinanceClient
        from urllib.parse import urlencode

        client = BinanceClient(dry_run=True)
        params = {"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "quantity": 0.001}
        signed = client._sign(params)

        assert "signature" in signed
        assert "timestamp" in signed
        assert "recvWindow" in signed

        # Reproduce the signature independently and compare
        payload = {k: v for k, v in signed.items() if k != "signature"}
        expected_sig = hmac.new(
            b"test_secret_abc",
            urlencode(payload).encode(),
            hashlib.sha256,
        ).hexdigest()
        assert signed["signature"] == expected_sig

    def test_sanitise_redacts_signature(self):
        from bot.client import BinanceClient
        params = {"symbol": "BTCUSDT", "signature": "abc123", "timestamp": 1234567890}
        sanitised = BinanceClient._sanitise(params)
        assert sanitised["signature"] == "***REDACTED***"
        assert sanitised["symbol"] == "BTCUSDT"
        assert sanitised["timestamp"] == 1234567890

    def test_sanitise_does_not_mutate_original(self):
        from bot.client import BinanceClient
        params = {"signature": "real_sig", "symbol": "ETHUSDT"}
        BinanceClient._sanitise(params)
        assert params["signature"] == "real_sig"  # original unchanged


# ---------------------------------------------------------------------------
# Successful POST
# ---------------------------------------------------------------------------

class TestPost:
    def test_post_returns_parsed_json_on_success(self):
        from bot.client import BinanceClient

        mock_response = _make_mock_response(
            {"orderId": 42, "status": "FILLED", "symbol": "BTCUSDT"}, 200
        )
        with patch("httpx.Client.post", return_value=mock_response):
            client = BinanceClient()
            result = client.post("/fapi/v1/order", {"symbol": "BTCUSDT"})

        assert result["orderId"] == 42
        assert result["status"] == "FILLED"

    def test_dry_run_returns_mock_response_without_http(self):
        from bot.client import BinanceClient

        client = BinanceClient(dry_run=True)
        result = client.post("/fapi/v1/order", {"symbol": "BTCUSDT", "type": "MARKET"})
        assert result["status"] == "DRY_RUN"
        assert result["symbol"] == "BTCUSDT"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_raises_binance_api_error_on_4xx(self):
        from bot.client import BinanceClient

        mock_response = _make_mock_response(
            {"code": -1121, "msg": "Invalid symbol."}, 400
        )
        with patch("httpx.Client.post", return_value=mock_response):
            client = BinanceClient()
            with pytest.raises(BinanceAPIError) as exc_info:
                client.post("/fapi/v1/order", {"symbol": "INVALID"})

        assert exc_info.value.code == -1121
        assert exc_info.value.status_code == 400
        assert "Invalid symbol" in exc_info.value.message

    def test_raises_binance_api_error_on_5xx(self):
        from bot.client import BinanceClient

        mock_response = _make_mock_response({"code": -1000, "msg": "Server error"}, 500)
        with patch("httpx.Client.post", return_value=mock_response):
            client = BinanceClient()
            with pytest.raises(BinanceAPIError) as exc_info:
                client.post("/fapi/v1/order", {})

        assert exc_info.value.status_code == 500

    def test_raises_timeout_error(self):
        import httpx as _httpx
        from bot.client import BinanceClient

        with patch("httpx.Client.post", side_effect=_httpx.TimeoutException("timed out")):
            client = BinanceClient()
            with pytest.raises(BinanceTimeoutError):
                client.post("/fapi/v1/order", {})

    def test_raises_network_error(self):
        import httpx as _httpx
        from bot.client import BinanceClient

        with patch("httpx.Client.post", side_effect=_httpx.NetworkError("unreachable")):
            client = BinanceClient()
            with pytest.raises(BinanceNetworkError):
                client.post("/fapi/v1/order", {})

    def test_api_error_has_user_hint_for_known_code(self):
        err = BinanceAPIError(status_code=400, code=-1121, message="Invalid symbol.")
        hint = err.user_hint()
        assert len(hint) > 0
        assert "symbol" in hint.lower()

    def test_api_error_user_hint_empty_for_unknown_code(self):
        err = BinanceAPIError(status_code=400, code=-9999, message="Unknown.")
        assert err.user_hint() == ""


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_client_closes_on_exit(self):
        from bot.client import BinanceClient

        with patch("httpx.Client") as mock_http_cls:
            mock_http_instance = MagicMock()
            mock_http_cls.return_value = mock_http_instance

            with BinanceClient() as client:
                pass

            mock_http_instance.close.assert_called_once()

    def test_dry_run_close_does_not_error(self):
        from bot.client import BinanceClient

        client = BinanceClient(dry_run=True)
        client.close()  # should not raise
