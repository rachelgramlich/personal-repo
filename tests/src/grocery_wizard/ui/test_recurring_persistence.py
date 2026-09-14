"""Tests that per-week recurring edits do not modify the saved template."""

from __future__ import annotations

from pathlib import Path

from src.grocery_wizard.shopping.recurring_weekly_items import (
    load_recurring_weekly_items,
    write_recurring_weekly_items,
)
from src.grocery_wizard.ui.app import _save_recurring_template

APP_PATH = Path(__file__).resolve().parents[4] / "src" / "grocery_wizard" / "ui" / "app.py"


def test_build_final_list_does_not_auto_persist_recurring_template() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    review_block = source.split("def _render_per_recipe_review", 1)[1].split(
        "def render_create_weekly_plan", 1
    )[0]
    assert "_persist_recurring_if_edited" not in review_block
    assert "_save_recurring_template" not in review_block


def test_save_recurring_template_writes_parsed_items(tmp_path: Path) -> None:
    path = tmp_path / "recurring_weekly_items.txt"
    write_recurring_weekly_items(path, ["berries", "milk"])
    _save_recurring_template("berries\nmilk\nyogurt", path=path)
    assert load_recurring_weekly_items(path) == ["berries", "milk", "yogurt"]
