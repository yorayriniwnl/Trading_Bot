.PHONY: install test test-cov lint run-market run-limit run-stop-limit dry-run run-ui sample-logs clean help

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## Create venv and install all dependencies
	python3.11 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

test:  ## Run all unit tests
	pytest tests/ -v

test-cov:  ## Run tests with coverage report (requires pytest-cov)
	pytest tests/ -v --cov=bot --cov-report=term-missing

lint:  ## Run ruff linter (install separately: pip install ruff)
	ruff check bot/ cli.py ui.py tests/

run-market:  ## Place a testnet MARKET buy order (requires .env)
	python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

run-limit:  ## Place a testnet LIMIT sell order (requires .env)
	python cli.py place --symbol BTCUSDT --side SELL --type LIMIT \
	  --quantity 0.001 --price 999999

run-stop-limit:  ## Place a testnet STOP_LIMIT buy order (requires .env)
	python cli.py place --symbol BTCUSDT --side BUY --type STOP_LIMIT \
	  --quantity 0.001 --price 45000 --stop-price 44500

dry-run:  ## Preview a LIMIT order without sending it (no .env needed)
	python cli.py place --symbol ETHUSDT --side BUY --type LIMIT \
	  --quantity 0.05 --price 3000 --dry-run

run-ui:  ## Launch the optional Streamlit UI
	streamlit run ui.py

sample-logs:  ## Generate clean sample MARKET and LIMIT logs (dry-run mode)
	python scripts/generate_sample_logs.py

clean:  ## Remove bytecode, logs, and venv
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	rm -rf .venv .pytest_cache logs/*.log
