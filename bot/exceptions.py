"""
exceptions.py — Typed exception hierarchy for the trading bot.

Having a single module for exceptions means callers can import from one
place and the hierarchy is easy to see at a glance.
"""


class TradingBotError(Exception):
    """Base class for all trading bot errors."""


class BinanceAPIError(TradingBotError):
    """
    Raised when the Binance API returns a non-2xx status or an error payload.

    Attributes:
        status_code: HTTP status code from the response.
        code:        Binance internal error code (e.g. -1121).
        message:     Human-readable error message from Binance.
    """

    # Common Binance Futures error codes for reference
    CODE_INVALID_SYMBOL = -1121
    CODE_INSUFFICIENT_BALANCE = -2019
    CODE_INVALID_PRICE = -1013
    CODE_INVALID_QUANTITY = -1111
    CODE_INVALID_TIMESTAMP = -1021
    CODE_BAD_API_KEY = -2014

    def __init__(self, status_code: int, code: int, message: str) -> None:
        self.status_code = status_code
        self.code = int(code)
        self.message = str(message)
        super().__init__(f"[HTTP {status_code}] Binance error {code}: {message}")

    def user_hint(self) -> str:
        """Return an actionable hint for known error codes."""
        hints = {
            self.CODE_INVALID_SYMBOL: (
                "Check the symbol format — must be uppercase and end in USDT or BUSD "
                "(e.g. BTCUSDT). Verify the pair exists on Binance Futures."
            ),
            self.CODE_INSUFFICIENT_BALANCE: (
                "Insufficient margin balance. Top up your Futures Testnet wallet at "
                "https://testnet.binancefuture.com."
            ),
            self.CODE_INVALID_PRICE: (
                "Price is outside the allowed range or violates tick-size rules. "
                "Try a price closer to the current market price."
            ),
            self.CODE_INVALID_QUANTITY: (
                "Quantity violates step-size or min-notional rules for this symbol."
            ),
            self.CODE_INVALID_TIMESTAMP: (
                "Request timestamp is out of sync. Check your system clock."
            ),
            self.CODE_BAD_API_KEY: (
                "API key is invalid or missing. Check your .env file."
            ),
        }
        return hints.get(self.code, "")


class BinanceNetworkError(TradingBotError):
    """Raised on connection / DNS failures."""


class BinanceTimeoutError(TradingBotError):
    """Raised when the request times out."""
