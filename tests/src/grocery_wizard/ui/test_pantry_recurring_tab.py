"""Tests for pantry/recurring tab layout and helpers."""

from __future__ import annotations

from pathlib import Path

from ui_source import pantry_tab_source, ui_source

APP_PATH = Path(__file__).resolve().parents[4] / "src" / "grocery_wizard" / "ui" / "app.py"


def test_weekly_recipe_tab_is_first_and_default() -> None:
    source = ui_source()
    assert '_TAB_WEEKLY = "Weekly recipe generation"' in source
    assert "_UI_TABS = (_TAB_WEEKLY, _TAB_ADD, _TAB_PANTRY)" in source
    app = APP_PATH.read_text(encoding="utf-8")
    assert "st.segmented_control(" in app
    assert "default=_TAB_WEEKLY" in app
    assert "if active_tab == _TAB_WEEKLY:" in app
    assert "render_create_weekly_plan()" in app


def test_pantry_and_recurring_share_one_tab() -> None:
    app = APP_PATH.read_text(encoding="utf-8")
    pantry_fn = pantry_tab_source()
    assert "def render_pantry_and_recurring()" in pantry_fn
    assert "elif active_tab == _TAB_ADD:" in app
    assert "render_pantry_and_recurring()" in app
    assert "### Pantry" in pantry_fn
    assert "### Recurring weekly items" in pantry_fn
    assert pantry_fn.index("### Recurring weekly items") < pantry_fn.index("### Pantry")
    assert "Save recurring template" not in pantry_fn
    assert "load_store_aisles" in pantry_fn
    assert '"Store aisle"' in pantry_fn
