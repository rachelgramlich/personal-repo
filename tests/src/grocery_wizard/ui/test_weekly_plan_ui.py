"""Regression tests for issue #29 weekly plan swap UI in app.py."""

from __future__ import annotations

from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[4] / "src" / "grocery_wizard" / "ui" / "app.py"
APP_FILE = str(APP_PATH)


def test_weekly_plan_has_per_meal_swap_buttons() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'st.button("↺", key=f"swap_meal_{index}"' in source
    assert "meal_col, swap_col = st.columns([8, 1])" in source
    assert "_apply_plan_swap" in source
    assert "replace_meals_in_plan(" in source


def test_weekly_plan_regenerate_preserves_rejected_names() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'st.button("↺ Re-generate everything"' in source
    assert "plan_rejected_names" in source
    assert "st.session_state.plan_rejected_names = []" in source


def test_weekly_plan_edit_manually_expander_has_text_area_only() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'st.expander("Edit manually"' in source
    assert "Swap or edit meals" not in source
    assert "plan_meals_to_swap" not in source
    assert 'key="swap_meals"' not in source
    assert "Swap selected" not in source


def test_scratch_plan_slot_first_manual_picker() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert "Choose recipe manually" in source
    assert "_render_slot_manual_picker" in source
    assert "plan_week_filter" in source
    assert "Keep these recipes" not in source
    assert 'st.expander("More options"' not in source
    assert "Fill remaining slots" in source


def test_weekly_plan_build_shows_per_meal_swap_and_edit_manually() -> None:
    """AppTest smoke test: Build my plan renders per-meal ↺ buttons and simplified expander."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.run(timeout=60)

    continue_buttons = [b for b in at.button if b.label == "Continue"]
    assert continue_buttons, "Weekly plan entry Continue button missing"
    continue_buttons[0].click().run(timeout=60)

    build_buttons = [b for b in at.button if b.label == "Build my plan"]
    assert build_buttons, "Build my plan button missing"
    build_buttons[0].click().run(timeout=60)

    swap_buttons = [b for b in at.button if b.label == "↺"]
    assert len(swap_buttons) >= 1, "Expected at least one per-meal ↺ swap button"

    regen = [b for b in at.button if b.label == "↺ Re-generate everything"]
    assert regen, "↺ Re-generate everything button missing"

    expander_labels = [e.label for e in at.expander]
    assert "Edit manually" in expander_labels
    assert "Swap or edit meals" not in expander_labels

    multiselect_labels = [m.label for m in at.multiselect]
    assert "Meals to replace" not in multiselect_labels

    swap_selected = [b for b in at.button if b.label == "Swap selected"]
    assert not swap_selected


def test_grocery_list_extra_items_before_create_button() -> None:
    """Issue #121: Extra items live in Grocery list options before Create grocery list."""
    source = APP_PATH.read_text(encoding="utf-8")
    section = source.split("### 2. Grocery list", 1)[1].split("def _render_grocery_result", 1)[0]

    create_idx = section.index('if st.button("Create grocery list"')
    options_block = section.split('with st.expander("Grocery list options"', 1)[1].split(
        'if st.button("Create grocery list"', 1
    )[0]
    assert 'key="grocery_pre_extra_items"' in options_block
    assert section.index('key="grocery_pre_extra_items"') < create_idx
