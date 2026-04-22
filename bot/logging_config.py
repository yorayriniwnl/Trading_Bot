import os
import sys
from pathlib import Path

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_FILE = PROJECT_ROOT / "logs" / "trading_bot.log"


def resolve_log_file(log_file: str | Path | None = None) -> Path:
    candidate = log_file or os.getenv("TRADING_BOT_LOG_FILE") or DEFAULT_LOG_FILE
    resolved = Path(candidate)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def setup_logging(log_file: str | Path | None = None) -> Path:
    """Configure loguru sinks: rotating file (DEBUG) + stderr (WARNING only)."""
    logger.remove()

    resolved_log_file = resolve_log_file(log_file)

    logger.add(
        resolved_log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    logger.add(
        sys.stderr,
        level="WARNING",
        format="{time:HH:mm:ss} | {level:<8} | {message}",
        colorize=True,
    )

    logger.debug("Logging initialised | file={}", resolved_log_file)
    return resolved_log_file
