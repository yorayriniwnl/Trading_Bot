"""
Generate clean sample MARKET and LIMIT logs for the submission package.

By default the script runs in dry-run mode so it works without credentials.
Use --live after configuring .env to produce real Binance Futures Testnet logs.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs" / "samples"


def build_cases(live: bool) -> list[tuple[str, list[str]]]:
    mode_args = [] if live else ["--dry-run"]
    return [
        (
            "market_order.log",
            [
                "place",
                "--symbol",
                "BTCUSDT",
                "--side",
                "BUY",
                "--type",
                "MARKET",
                "--quantity",
                "0.002",
                *mode_args,
            ],
        ),
        (
            "limit_order.log",
            [
                "place",
                "--symbol",
                "ETHUSDT",
                "--side",
                "BUY",
                "--type",
                "LIMIT",
                "--quantity",
                "0.01",
                "--price",
                "3000",
                *mode_args,
            ],
        ),
    ]


def ensure_live_credentials() -> None:
    missing = [
        name
        for name in ("BINANCE_TESTNET_API_KEY", "BINANCE_TESTNET_SECRET")
        if not os.getenv(name)
    ]
    if missing:
        raise SystemExit(
            "Cannot generate live logs because these variables are missing: "
            + ", ".join(missing)
        )


def run_case(log_name: str, args: list[str], *, live: bool) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / log_name
    if log_path.exists():
        log_path.unlink()

    env = os.environ.copy()
    env["TRADING_BOT_LOG_FILE"] = str(log_path)

    completed = subprocess.run(
        [sys.executable, "cli.py", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        mode = "live" if live else "dry-run"
        raise SystemExit(f"Sample log generation failed for {log_name} ({mode} mode).")
    return log_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate clean sample log files for MARKET and LIMIT orders.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Submit real Binance Futures Testnet orders instead of dry-run previews.",
    )
    args = parser.parse_args()

    if args.live:
        ensure_live_credentials()

    generated = [run_case(name, case_args, live=args.live) for name, case_args in build_cases(args.live)]
    mode = "live testnet" if args.live else "dry-run"
    print(f"Generated {len(generated)} sample log files in {mode} mode:")
    for path in generated:
        print(f" - {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
