"""Concatenated Streamlit UI sources for regression string checks."""

from __future__ import annotations

from pathlib import Path

UI_ROOT = Path(__file__).resolve().parents[4] / "src" / "grocery_wizard" / "ui"

_UI_MODULE_PATHS = (
    "app.py",
    "tabs.py",
    "sections/weekly_plan.py",
    "sections/add_recipe.py",
    "sections/pantry_recurring.py",
    "grocery_helpers.py",
    "meal_plan_filters.py",
)


def ui_source() -> str:
    chunks = [(UI_ROOT / rel).read_text(encoding="utf-8") for rel in _UI_MODULE_PATHS]
    return "\n\n".join(chunks)


def pantry_tab_source() -> str:
    return (UI_ROOT / "sections" / "pantry_recurring.py").read_text(encoding="utf-8")
