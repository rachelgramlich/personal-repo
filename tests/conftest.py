"""Pytest configuration for grocery_wizard tests."""

from __future__ import annotations

import sys
from pathlib import Path

_UI_TEST_HELPERS = Path(__file__).resolve().parent / "src" / "grocery_wizard" / "ui"
if str(_UI_TEST_HELPERS) not in sys.path:
    sys.path.insert(0, str(_UI_TEST_HELPERS))
