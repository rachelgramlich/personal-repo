"""Tests for grocery output step (added/removed summary and final list editing)."""

from __future__ import annotations

from pathlib import Path

from src.grocery_wizard.ui.app import _apply_run_removals

APP_PATH = Path(__file__).resolve().parents[4] / "src" / "grocery_wizard" / "ui" / "app.py"


def test_apply_run_removals_filters_matching_lines() -> None:
    items = ["2 cups milk", "eggs", "bread"]
    assert _apply_run_removals(items, {"milk"}) == ["eggs", "bread"]


def test_output_step_shows_added_removed_and_editable_grocery_list() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    result_block = source.split("def _render_grocery_result", 1)[1].split(
        'if __name__ == "__main__"', 1
    )[0]
    assert "_render_added_and_removed_summary" in result_block
    assert "Added items" in source
    assert "Removed items (pantry)" in source
    assert "Edit the list below before copying or downloading." in result_block
    assert 'key="grocery_final_list"' in result_block
    assert "disabled=True" not in result_block
