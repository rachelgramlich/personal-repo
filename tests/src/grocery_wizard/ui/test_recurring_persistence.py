"""Tests that per-week recurring edits do not modify the saved template."""

from __future__ import annotations

from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[4] / "src" / "grocery_wizard" / "ui" / "app.py"


def test_build_final_list_does_not_auto_persist_recurring_template() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    review_block = source.split("def _render_per_recipe_review", 1)[1].split(
        "def render_create_weekly_plan", 1
    )[0]
    assert "_persist_recurring_if_edited" not in review_block


def test_pantry_tab_has_no_bulk_recurring_editor() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    pantry_fn = source.split("def render_pantry_and_recurring()", 1)[1].split(
        "def _recipes_ingredient_cache_key", 1
    )[0]
    assert "Save recurring template" not in pantry_fn
    assert "pantry_tab_recurring_template_editor" not in pantry_fn
    assert "Bulk edit the saved recurring template" not in pantry_fn
