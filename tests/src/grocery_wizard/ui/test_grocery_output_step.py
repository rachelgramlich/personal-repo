"""Tests for grocery output step (added/removed summary and final list editing)."""

from __future__ import annotations

from pathlib import Path

from ui_source import ui_source

from src.grocery_wizard.ui.grocery_helpers import apply_run_removals

APP_PATH = Path(__file__).resolve().parents[4] / "src" / "grocery_wizard" / "ui" / "app.py"


def test_apply_run_removals_filters_matching_lines() -> None:
    items = ["2 cups milk", "eggs", "bread"]
    assert apply_run_removals(items, {"milk"}) == ["eggs", "bread"]


def test_output_step_shows_added_removed_and_editable_grocery_list() -> None:
    source = ui_source()
    result_block = source.split("def _render_grocery_result", 1)[1].split(
        'if __name__ == "__main__"', 1
    )[0]
    assert "_render_added_and_removed_summary" in result_block
    assert "Summary (build result)" in source
    assert "Added: recurring items and pasted extras" in source
    assert "Removed: items in the pantry" in source
    assert 'with st.expander("Adjust this week\'s list"' in source
    assert "Add to grocery list from pantry (1x)" in source
    assert "Remove from grocery list (1x)" in source
    assert "Remove and add to pantry" not in source
    assert 'with st.expander("Customize list"' not in result_block
    assert "### Customize list" in result_block
    assert "Extra items (one per line)" not in result_block
    assert "Edit the list below before copying." in result_block
    assert "render_copy_download" in result_block
    assert 'key="grocery_edit_meals"' not in result_block
    assert 'key="grocery_update_list"' not in result_block
    assert 'key="grocery_final_list"' in result_block
    assert "disabled=True" not in result_block
