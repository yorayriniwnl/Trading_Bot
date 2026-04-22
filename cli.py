"""
cli.py - Typer CLI for the Binance Futures Testnet trading bot.

Usage:
    python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
    python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 50000
    python cli.py place --symbol BTCUSDT --side BUY --type STOP_LIMIT \
        --quantity 0.001 --price 45000 --stop-price 44500
    python cli.py place --symbol ETHUSDT --side BUY --type LIMIT \
        --quantity 0.05 --price 3000 --dry-run --no-validate-exchange
"""
from __future__ import annotations

from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bot.execution import OrderRequest, execute_order, prepare_order_request
from bot.exceptions import BinanceAPIError, BinanceNetworkError, BinanceTimeoutError
from bot.orders import OrderResult
from bot.runtime import initialize_runtime

app = typer.Typer(
    name="trading-bot",
    help="Binance Futures Testnet order placement CLI",
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


@app.callback()
def main() -> None:
    """Binance Futures Testnet order placement CLI."""
    initialize_runtime()


def _print_order_request_table(request: OrderRequest) -> None:
    title = "Order Request Summary" + (" [yellow](DRY RUN)[/yellow]" if request.dry_run else "")
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Field", style="dim", width=16)
    table.add_column("Value")

    table.add_row("Symbol", request.symbol)
    side_display = (
        f"[green]{request.side}[/green]"
        if request.side == "BUY"
        else f"[red]{request.side}[/red]"
    )
    table.add_row("Side", side_display)
    table.add_row("Order Type", request.order_type)
    table.add_row("Quantity", str(request.quantity))
    if request.price is not None:
        table.add_row("Price", str(request.price))
    if request.stop_price is not None:
        table.add_row("Stop Price", str(request.stop_price))
    if request.order_type != "MARKET":
        table.add_row("TIF", request.time_in_force)
    if request.dry_run:
        table.add_row("Mode", "[yellow]DRY RUN - no order will be sent[/yellow]")

    console.print()
    console.print(table)
    console.print()


def _print_success(result: OrderResult, dry_run: bool) -> None:
    dry_label = " [yellow](DRY RUN)[/yellow]" if dry_run else ""
    content = (
        f"[bold]Order ID:[/bold]      {result.orderId}\n"
        f"[bold]Symbol:[/bold]        {result.symbol}\n"
        f"[bold]Type:[/bold]          {result.type}\n"
        f"[bold]Status:[/bold]        [green]{result.status}[/green]\n"
        f"[bold]Executed Qty:[/bold]  {result.executedQty}\n"
        f"[bold]Avg Price:[/bold]     {result.avgPrice}"
    )
    title = (
        f"{'Order Placed Successfully' if not dry_run else 'Dry Run Complete'}"
        f"{dry_label}"
    )
    console.print(Panel(content, title=title, border_style="green" if not dry_run else "yellow"))


def _print_failure(message: str, hint: str = "") -> None:
    body = f"[red]{message}[/red]"
    if hint:
        body += f"\n\n[dim]Hint: {hint}[/dim]"
    err_console.print(Panel(body, title="[bold red]Order Failed[/bold red]", border_style="red"))


@app.command()
def place(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Trading pair, e.g. BTCUSDT"),
    side: str = typer.Option(..., "--side", help="BUY or SELL"),
    order_type: str = typer.Option(..., "--type", "-t", help="MARKET | LIMIT | STOP_LIMIT"),
    quantity: float = typer.Option(..., "--quantity", "-q", help="Order quantity (positive float, max 8 dp)"),
    price: Optional[float] = typer.Option(None, "--price", "-p", help="Limit price (required for LIMIT / STOP_LIMIT)"),
    stop_price: Optional[float] = typer.Option(None, "--stop-price", help="Trigger price (required for STOP_LIMIT)"),
    time_in_force: str = typer.Option("GTC", "--tif", help="Time-in-force: GTC | IOC | FOK"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the order without sending it to Binance"),
    validate_exchange: bool = typer.Option(
        True,
        "--validate-exchange/--no-validate-exchange",
        help=(
            "Check Binance Testnet symbol filters before submission. "
            "Disable this for fully offline dry-run usage."
        ),
    ),
) -> None:
    """Place a Futures Testnet order (MARKET, LIMIT, or STOP_LIMIT)."""
    try:
        request = prepare_order_request(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            dry_run=dry_run,
            validate_exchange_metadata=validate_exchange,
        )
    except ValueError as exc:
        logger.warning("Validation failed: {}", exc)
        _print_failure(str(exc))
        raise typer.Exit(code=1)

    _print_order_request_table(request)

    try:
        result = execute_order(request)
    except BinanceAPIError as exc:
        logger.error("Binance API error: {}", exc)
        _print_failure(str(exc), hint=exc.user_hint())
        raise typer.Exit(code=1)
    except (BinanceNetworkError, BinanceTimeoutError) as exc:
        logger.error("Network/timeout error: {}", exc)
        _print_failure(str(exc))
        raise typer.Exit(code=1)
    except EnvironmentError as exc:
        logger.critical("Environment misconfiguration: {}", exc)
        _print_failure(str(exc))
        raise typer.Exit(code=1)
    except Exception as exc:
        logger.exception("Unexpected error during order placement")
        _print_failure(f"Unexpected error: {exc}")
        raise typer.Exit(code=1)

    _print_success(result, request.dry_run)


if __name__ == "__main__":
    app()
