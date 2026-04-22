"""
conftest.py — Pytest configuration at project root.

Adds the project root to sys.path so that `from bot.xxx import yyy`
resolves correctly when running `pytest` from any working directory.
"""
import sys
from pathlib import Path

# Ensure the project root is on the path regardless of where pytest is invoked
sys.path.insert(0, str(Path(__file__).parent))
