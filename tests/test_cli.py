from typer.testing import CliRunner

import cli


runner = CliRunner()


def test_place_dry_run_succeeds_without_credentials(monkeypatch):
    monkeypatch.delenv("BINANCE_TESTNET_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_TESTNET_SECRET", raising=False)

    result = runner.invoke(
        cli.app,
        [
            "place",
            "--symbol",
            "ETHUSDT",
            "--side",
            "BUY",
            "--type",
            "LIMIT",
            "--quantity",
            "0.05",
            "--price",
            "3000",
            "--dry-run",
            "--no-validate-exchange",
        ],
    )

    assert result.exit_code == 0
    assert "Dry Run Complete" in result.output
