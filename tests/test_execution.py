from unittest.mock import patch

import pytest

from bot.execution import OrderRequest, execute_order, prepare_order_request, submit_order
from bot.orders import OrderResult


def test_prepare_order_request_normalises_limit_order():
    with patch("bot.execution.validate_exchange_rules") as mock_exchange_validation:
        request = prepare_order_request(
            symbol=" ethusdt ",
            side="buy",
            order_type="limit",
            quantity="0.05",
            price=3000,
            time_in_force="ioc",
            dry_run=True,
            validate_exchange_metadata=True,
        )

    assert request == OrderRequest(
        symbol="ETHUSDT",
        side="BUY",
        order_type="LIMIT",
        quantity=0.05,
        price=3000.0,
        stop_price=None,
        time_in_force="IOC",
        dry_run=True,
    )
    mock_exchange_validation.assert_called_once_with(
        symbol="ETHUSDT",
        order_type="LIMIT",
        quantity=0.05,
        price=3000.0,
        stop_price=None,
    )


def test_prepare_order_request_rejects_invalid_tif_for_limit_order():
    with pytest.raises(ValueError, match="time-in-force"):
        prepare_order_request(
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            quantity=0.001,
            price=50000,
            time_in_force="DAY",
        )


def test_prepare_order_request_uses_default_tif_for_market_order():
    request = prepare_order_request(
        symbol="BTCUSDT",
        side="SELL",
        order_type="MARKET",
        quantity=0.002,
        time_in_force="DAY",
    )

    assert request.order_type == "MARKET"
    assert request.time_in_force == "GTC"
    assert request.price is None
    assert request.stop_price is None


def test_execute_order_delegates_to_limit_order():
    request = OrderRequest(
        symbol="ETHUSDT",
        side="BUY",
        order_type="LIMIT",
        quantity=0.05,
        price=3000.0,
        time_in_force="GTC",
        dry_run=True,
    )
    expected = OrderResult(
        orderId="1",
        symbol="ETHUSDT",
        status="DRY_RUN",
        executedQty="0",
        avgPrice="0",
        type="LIMIT",
    )

    with patch("bot.execution.BinanceClient") as mock_client_cls, patch(
        "bot.execution.place_limit_order",
        return_value=expected,
    ) as mock_place_limit:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        result = execute_order(request)

    assert result == expected
    mock_client_cls.assert_called_once_with(dry_run=True)
    mock_place_limit.assert_called_once_with(
        mock_client,
        "ETHUSDT",
        "BUY",
        0.05,
        3000.0,
        "GTC",
    )


def test_submit_order_returns_request_and_result():
    expected = OrderResult(
        orderId="0",
        symbol="BTCUSDT",
        status="DRY_RUN",
        executedQty="0",
        avgPrice="0",
        type="MARKET",
    )

    with patch("bot.execution.execute_order", return_value=expected) as mock_execute:
        request, result = submit_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.001,
            dry_run=True,
        )

    assert request.order_type == "MARKET"
    assert request.dry_run is True
    assert result == expected
    mock_execute.assert_called_once_with(request)


def test_prepare_order_request_propagates_exchange_validation_error():
    with patch(
        "bot.execution.validate_exchange_rules",
        side_effect=ValueError("price must align with tick size 0.10 for BTCUSDT."),
    ):
        with pytest.raises(ValueError, match="tick size"):
            prepare_order_request(
                symbol="BTCUSDT",
                side="BUY",
                order_type="LIMIT",
                quantity=0.002,
                price=60000.05,
                validate_exchange_metadata=True,
            )
