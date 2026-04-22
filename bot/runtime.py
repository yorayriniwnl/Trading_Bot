"""
Shared runtime bootstrap helpers for CLI and Streamlit entry points.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from .logging_config import setup_logging


def initialize_runtime(log_file: str | Path | None = None) -> Path:
    """Load environment variables and configure logging for an app entry point."""
    load_dotenv()
    return setup_logging(log_file)
