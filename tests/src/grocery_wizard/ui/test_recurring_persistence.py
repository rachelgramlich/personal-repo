"""Tests that per-week recurring edits do not modify the saved template."""

from __future__ import annotations

from ui_source import pantry_tab_source, ui_source


def test_build_final_list_does_not_auto_persist_recurring_template() -> None:
    source = ui_source()
    review_block = source.split("def _render_per_recipe_review", 1)[1].split(
        "def render_create_weekly_plan", 1
    )[0]
    assert "_persist_recurring_if_edited" not in review_block


def test_pantry_tab_has_no_bulk_recurring_editor() -> None:
    pantry_fn = pantry_tab_source()
    assert "Save recurring template" not in pantry_fn
    assert "pantry_tab_recurring_template_editor" not in pantry_fn
    assert "Bulk edit the saved recurring template" not in pantry_fn
