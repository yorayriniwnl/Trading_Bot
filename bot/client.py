"""
client.py — HMAC-signed httpx wrapper for Binance Futures Testnet.

Responsibilities:
  - Read credentials from environment (never accept them as constructor args)
  - Sign every request with HMAC-SHA256 (timestamp + recvWindow)
  - Log sanitised request params and raw responses at DEBUG level
  - Raise typed exceptions (BinanceAPIError / BinanceNetworkError / BinanceTimeoutError)
  - Support a dry_run mode that skips the actual HTTP call
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from loguru import logger

from .exceptions import BinanceAPIError, BinanceNetworkError, BinanceTimeoutError

BASE_URL = "https://testnet.binancefuture.com"
RECV_WINDOW = 5000  # ms — tight window reduces replay-attack surface


class BinanceClient:
    """Thin authenticated client for the Binance Futures Testnet REST API."""

    def __init__(self, *, dry_run: bool = False) -> None:
        """
        Args:
            dry_run: When True, sign and validate requests but skip the HTTP call.
                     Returns a mock response for display/testing without needing
                     real credentials or network access.
        """
        self.dry_run = dry_run
        if dry_run:
            self._api_key = os.getenv("BINANCE_TESTNET_API_KEY", "dry_run_api_key")
            self._api_secret = os.getenv("BINANCE_TESTNET_SECRET", "dry_run_secret")
        else:
            self._api_key = self._require_env("BINANCE_TESTNET_API_KEY")
            self._api_secret = self._require_env("BINANCE_TESTNET_SECRET")

        if not dry_run:
            self._http = httpx.Client(
                base_url=BASE_URL,
                timeout=httpx.Timeout(10.0, connect=5.0),
                headers={"X-MBX-APIKEY": self._api_key},
            )
        logger.debug(
            "BinanceClient initialised | base_url={} dry_run={}",
            BASE_URL,
            dry_run,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def post(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        POST to *endpoint* with HMAC-signed *params*.

        Logging contract:
          DEBUG  - sanitised params before sending (secret never appears)
          DEBUG  - raw response body on success
          ERROR  - full response body and Binance error code on failure

        Returns the parsed JSON response dict.

        Raises:
            BinanceAPIError      - non-2xx HTTP response from Binance
            BinanceNetworkError  - connection / DNS failure
            BinanceTimeoutError  - request exceeded timeout
        """
        signed_params = self._sign(params)
        self._log_request(endpoint, signed_params)

        if self.dry_run:
            mock = self._dry_run_response(params)
            logger.debug("DRY RUN - skipping HTTP call, returning mock response: {}", mock)
            return mock

        try:
            response = self._http.post(endpoint, data=signed_params)
        except httpx.TimeoutException as exc:
            logger.error("Request timed out | endpoint={} error={}", endpoint, exc)
            raise BinanceTimeoutError(
                f"Request to {endpoint} timed out. "
                "Check your network or increase RECV_WINDOW."
            ) from exc
        except httpx.NetworkError as exc:
            logger.error("Network error | endpoint={} error={}", endpoint, exc)
            raise BinanceNetworkError(
                f"Network error reaching {BASE_URL}{endpoint}: {exc}"
            ) from exc

        return self._handle_response(response, endpoint)

    def close(self) -> None:
        if not self.dry_run and hasattr(self, "_http"):
            self._http.close()

    def __enter__(self) -> "BinanceClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_env(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise EnvironmentError(
                f"Required environment variable '{name}' is not set. "
                "Copy .env.example to .env and fill in your Testnet credentials."
            )
        return value

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        """Append timestamp, recvWindow, and HMAC-SHA256 signature."""
        signed = dict(params)
        signed["timestamp"] = int(time.time() * 1000)
        signed["recvWindow"] = RECV_WINDOW
        query_string = urlencode(signed)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signed["signature"] = signature
        return signed

    @staticmethod
    def _sanitise(params: dict[str, Any]) -> dict[str, Any]:
        """Return a copy with the HMAC signature redacted for safe logging."""
        return {
            k: ("***REDACTED***" if k == "signature" else v)
            for k, v in params.items()
        }

    def _log_request(self, endpoint: str, params: dict[str, Any]) -> None:
        logger.debug("POST {} | params={}", endpoint, self._sanitise(params))

    @staticmethod
    def _handle_response(
        response: httpx.Response, endpoint: str
    ) -> dict[str, Any]:
        """Parse response JSON; raise BinanceAPIError on non-2xx."""
        try:
            body: dict[str, Any] = response.json()
        except Exception:
            body = {"raw": response.text}

        if response.is_success:
            logger.debug("<- {} {} | body={}", response.status_code, endpoint, body)
            return body

        code = body.get("code", -1)
        message = body.get("msg", response.text or "Unknown error")
        logger.error(
            "<- {} {} | binance_code={} msg={}",
            response.status_code,
            endpoint,
            code,
            message,
        )
        raise BinanceAPIError(
            status_code=response.status_code,
            code=int(code),
            message=str(message),
        )

    @staticmethod
    def _dry_run_response(params: dict[str, Any]) -> dict[str, Any]:
        """Return a plausible mock response for dry-run mode."""
        return {
            "orderId": 0,
            "symbol": params.get("symbol", "UNKNOWN"),
            "status": "DRY_RUN",
            "executedQty": "0",
            "avgPrice": "0",
            "type": params.get("type", "UNKNOWN"),
            "side": params.get("side", "UNKNOWN"),
            "origQty": str(params.get("quantity", "0")),
            "price": str(params.get("price", "0")),
        }
