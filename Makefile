.PHONY: install test test-cov lint run-market run-limit run-stop-limit dry-run run-ui sample-logs clean help

PYTHON ?= python

ifeq ($(OS),Windows_NT)
VENV_PYTHON = .venv/Scripts/python.exe
else
VENV_PYTHON = .venv/bin/python
endif

PIP = $(VENV_PYTHON) -m pip

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## Create venv and install all dependencies
	$(PYTHON) -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e .[dev]

test:  ## Run all unit tests
	$(VENV_PYTHON) -m pytest tests/ -v

test-cov:  ## Run tests with coverage report (requires pytest-cov)
	$(VENV_PYTHON) -m pytest tests/ -v --cov=bot --cov-report=term-missing

lint:  ## Run ruff linter (install separately: pip install ruff)
	$(VENV_PYTHON) -m ruff check bot/ cli.py ui.py tests/

run-market:  ## Place a testnet MARKET buy order (requires .env)
	$(VENV_PYTHON) cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

run-limit:  ## Place a testnet LIMIT sell order (requires .env)
	$(VENV_PYTHON) cli.py place --symbol BTCUSDT --side SELL --type LIMIT \
	  --quantity 0.001 --price 999999

run-stop-limit:  ## Place a testnet STOP_LIMIT buy order (requires .env)
	$(VENV_PYTHON) cli.py place --symbol BTCUSDT --side BUY --type STOP_LIMIT \
	  --quantity 0.001 --price 45000 --stop-price 44500

dry-run:  ## Preview a LIMIT order without sending it (no .env needed)
	$(VENV_PYTHON) cli.py place --symbol ETHUSDT --side BUY --type LIMIT \
	  --quantity 0.05 --price 3000 --dry-run

run-ui:  ## Launch the optional Streamlit UI
	$(VENV_PYTHON) -m streamlit run ui.py

sample-logs:  ## Generate clean sample MARKET and LIMIT logs (dry-run mode)
	$(VENV_PYTHON) scripts/generate_sample_logs.py

clean:  ## Remove bytecode, logs, and venv
	$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(path, ignore_errors=True) for path in (Path('.venv'), Path('.pytest_cache'), Path('build'), Path('dist'))]; [shutil.rmtree(path, ignore_errors=True) for path in Path('.').rglob('__pycache__')]; [path.unlink(missing_ok=True) for pattern in ('*.pyc', 'logs/*.log', 'streamlit*.log') for path in Path('.').glob(pattern)]"
