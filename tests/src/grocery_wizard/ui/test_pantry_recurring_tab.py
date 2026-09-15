"""Tests for pantry/recurring tab layout and helpers."""

from __future__ import annotations

from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[4] / "src" / "grocery_wizard" / "ui" / "app.py"


def test_weekly_recipe_tab_is_first_and_default() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert "_TAB_WEEKLY = \"Weekly recipe generation\"" in source
    assert "_UI_TABS = (_TAB_WEEKLY, _TAB_ADD, _TAB_PANTRY)" in source
    assert "st.segmented_control(" in source
    assert "default=_TAB_WEEKLY" in source
    assert "if active_tab == _TAB_WEEKLY:" in source
    assert "render_create_weekly_plan()" in source


def test_pantry_and_recurring_share_one_tab() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert "def render_pantry_and_recurring()" in source
    assert "elif active_tab == _TAB_ADD:" in source
    assert "render_pantry_and_recurring()" in source
    pantry_fn = source.split("def render_pantry_and_recurring()", 1)[1].split(
        "def _recipes_ingredient_cache_key", 1
    )[0]
    assert "### Pantry" in pantry_fn
    assert "### Recurring weekly items" in pantry_fn
    assert "load_store_aisles" in pantry_fn
    assert 'st.selectbox(\n            "Store aisle"' in pantry_fn or '"Store aisle"' in pantry_fn
