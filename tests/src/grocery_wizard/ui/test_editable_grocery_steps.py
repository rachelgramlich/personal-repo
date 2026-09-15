"""Tests for editable review and final grocery/meals text areas."""

from __future__ import annotations

from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[4] / "src" / "grocery_wizard" / "ui" / "app.py"


def test_start_recipe_review_formats_notion_storage_lines() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    start_block = source.split("def _start_recipe_review", 1)[1].split(
        "def _render_per_recipe_review", 1
    )[0]
    assert "format_ingredients_for_review" in start_block


def test_per_recipe_review_initializes_widget_keys_without_value_param() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    review_block = source.split("def _render_per_recipe_review", 1)[1].split(
        "def render_create_weekly_plan", 1
    )[0]
    assert "if widget_key not in st.session_state:" in review_block
    assert "st.session_state[widget_key] = original_text" in review_block
    assert "value=original_text" not in review_block


def test_final_step_meals_and_grocery_use_separate_fingerprints() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    result_block = source.split("def _render_grocery_result", 1)[1].split(
        'if __name__ == "__main__"', 1
    )[0]
    assert "meals_final_list_fingerprint" in result_block
    assert "grocery_final_list_fingerprint" in result_block
    assert "meals_fingerprint = tuple(meals)" in result_block
    assert "grocery_fingerprint = (tuple(final_items),)" in result_block
    assert "disabled=True" not in result_block
    assert 'key="meals_final_list"' in result_block
    assert "meals_display" not in result_block


def test_copy_buttons_read_session_state_after_text_areas() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    result_block = source.split("def _render_grocery_result", 1)[1].split(
        'if __name__ == "__main__"', 1
    )[0]
    meals_idx = result_block.index('key="meals_final_list"')
    meals_copy_idx = result_block.index("meals_for_copy")
    assert meals_idx < meals_copy_idx
    grocery_idx = result_block.index('key="grocery_final_list"')
    grocery_copy_idx = result_block.index("grocery_for_copy")
    assert grocery_idx < grocery_copy_idx
    assert "_render_copy_button(meals_for_copy" in result_block
    assert "_render_copy_button(grocery_for_copy" in result_block


def test_clear_grocery_result_clears_meals_and_grocery_fingerprints() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    clear_block = source.split("def _clear_grocery_result", 1)[1].split(
        "def _invalidate_stale_grocery_result", 1
    )[0]
    assert "meals_final_list_fingerprint" in clear_block
    assert "grocery_final_list_fingerprint" in clear_block
    assert "_clear_grocery_pre_extra_items" in clear_block


def test_grocery_pre_extra_items_cleared_with_session_overrides() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    overrides_block = source.split("def _clear_grocery_session_overrides", 1)[1].split(
        "def _effective_recurring_items", 1
    )[0]
    assert "_bump_grocery_pre_extra_items_widget" in overrides_block
