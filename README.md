# Binance Futures Testnet Trading Bot

Python trading bot for the Binance USDT-M Futures Testnet hiring task. The project places `MARKET` and `LIMIT` orders from a CLI, includes `STOP_LIMIT` as a bonus order type, supports both `BUY` and `SELL`, logs every request/response/error to file, and keeps the code separated into client, execution, validation, and presentation layers.

Bonus features included:

- `STOP_LIMIT` order support
- optional premium Streamlit UI with a 3D trading-desk presentation built on the same backend workflow as the CLI
- exchange-filter preflight validation using Binance Testnet `exchangeInfo`

## Tech Stack

- Python 3.x
- `httpx` for direct signed REST calls
- `typer` + `rich` for CLI UX
- `loguru` for rotating file logs
- `python-dotenv` for credential loading
- `streamlit` for the optional UI

## Project Structure

```text
trading_bot/
|- bot/
|  |- client.py
|  |- exchange_info.py
|  |- execution.py
|  |- exceptions.py
|  |- logging_config.py
|  |- orders.py
|  `- validators.py
|- logs/
|  `- samples/
|- scripts/
|  `- generate_sample_logs.py
|- tests/
|- cli.py
|- ui.py
|- requirements.txt
`- pyproject.toml
```

## Features

- Places `MARKET`, `LIMIT`, and `STOP_LIMIT` orders on `https://testnet.binancefuture.com`
- Supports both `BUY` and `SELL`
- Validates CLI input before submission
- Prints a request summary plus response details including `orderId`, `status`, `executedQty`, and `avgPrice`
- Logs sanitized API requests, API responses, and errors to file
- Handles invalid input, Binance API errors, missing credentials, timeouts, and network failures
- Uses a shared execution path so the CLI and UI behave consistently
- Performs optional preflight checks against Binance symbol rules like `tickSize`, `stepSize`, and `MIN_NOTIONAL`

## Setup

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install -r requirements.txt
python -m pip install -e .[dev]
```

If you prefer not to activate the virtual environment on Windows, run commands with
`.\.venv\Scripts\python.exe` explicitly.

### 3. Configure Binance Futures Testnet credentials

Copy `.env.example` to `.env` and fill in your Binance Futures Testnet API key and secret:

```env
BINANCE_TESTNET_API_KEY=your_api_key_here
BINANCE_TESTNET_SECRET=your_secret_here
```

## CLI Usage

### MARKET order

Dry-run:

```bash
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.002 --dry-run
```

Live testnet:

```bash
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.002
```

### LIMIT order

Dry-run:

```bash
python cli.py place --symbol ETHUSDT --side BUY --type LIMIT --quantity 0.01 --price 3000 --dry-run
```

Live testnet:

```bash
python cli.py place --symbol ETHUSDT --side BUY --type LIMIT --quantity 0.01 --price 3000
```

### STOP_LIMIT order

```bash
python cli.py place --symbol BTCUSDT --side SELL --type STOP_LIMIT --quantity 0.002 --price 60000 --stop-price 59950 --dry-run
```

### Offline mode

If you want the CLI to skip the Binance metadata preflight check, use:

```bash
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.002 --dry-run --no-validate-exchange
```

## Optional UI

Run the Streamlit UI:

```bash
streamlit run ui.py
```

The UI uses the same `prepare_order_request()` and `execute_order()` workflow as the CLI, so validation and execution stay aligned. The current version presents the bot as a cinematic 3D trading deck with persistent response memory, command mirroring, and session activity tracking.

The desk also exposes the same exchange-metadata preflight toggle as the CLI, so offline dry-runs and stricter Binance filter checks stay in sync.

## Logs

Default log file:

```text
logs/trading_bot.log
```

Generate clean submission-ready sample logs:

```bash
python scripts/generate_sample_logs.py
```

Generate live sample logs after adding real testnet credentials:

```bash
python scripts/generate_sample_logs.py --live
```

Included sample log targets:

- `logs/samples/market_order.log`
- `logs/samples/limit_order.log`

## Testing

Run the full test suite:

```bash
python -m pytest tests -v
```

## Assumptions

- Public repositories should never include live API credentials.
- Included sample logs can be generated in dry-run mode without credentials; run the provided script with `--live` before final submission if live testnet logs are required.
- The bot validates common symbol rules before submission, but Binance can still reject orders for dynamic reasons such as current percent-price limits or account state.

## Why This Structure

- `client.py` handles signing, HTTP communication, and API error translation.
- `orders.py` contains reusable order-placement functions only.
- `execution.py` centralizes request preparation so the CLI and UI share the same behavior.
- `validators.py` and `exchange_info.py` keep local validation separate from exchange-rule validation.
- `logging_config.py` centralizes file logging setup and supports custom log destinations for sample generation.
