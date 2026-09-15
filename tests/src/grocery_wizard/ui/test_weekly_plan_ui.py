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


def test_weekly_plan_has_no_bulk_edit_manually_expander() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'st.expander("Edit manually"' not in source
    assert 'key="plan_meals_text"' not in source
    assert "_write_plan_names" in source


def test_scratch_plan_slot_first_manual_picker() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert "Choose recipe manually" in source
    assert "_render_slot_manual_picker" in source
    assert "plan_week_filter" in source
    assert "_week_level_plan_filter_columns" in source
    assert "Keep these recipes" not in source
    assert 'st.expander("More options"' not in source
    assert "Fill remaining slots" in source


def test_weekly_plan_build_shows_per_meal_swap() -> None:
    """AppTest smoke test: Build my plan renders per-meal ↺ buttons."""
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
    assert "Edit manually" not in expander_labels
    assert "Swap or edit meals" not in expander_labels

    multiselect_labels = [m.label for m in at.multiselect]
    assert "Meals to replace" not in multiselect_labels

    swap_selected = [b for b in at.button if b.label == "Swap selected"]
    assert not swap_selected


def test_dev_mode_exposes_collapsed_dev_tools_expander() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert '_render_dev_jump_tools(db)' in source
    assert 'st.expander("Dev tools", expanded=False)' in source
    assert '_weekly_plan_mode() != "dev"' in source
    assert "commit_dev_jump" in source
    assert "pick_default_recipe_names" in source
    assert "Meals filled: auto" in source
    assert "Meals filled: manual" in source
    assert 'key="dev_jump_manual_recipes"' in source
    assert 'st.markdown("#### Meals filled")' not in source
    assert '"Choose recipes manually"' in source
    assert '"Final list"' in source
    dev_section = source.split('st.expander("Dev tools"', 1)[1].split("def _render_weekly_plan_entry", 1)[0]
    assert "DEV_JUMP_FLOW_ORDER" in dev_section
    assert "for step in DEV_JUMP_FLOW_ORDER:\n            _dev_jump_bullet(step)" in dev_section
    bullets_end = dev_section.index("all_names = sorted")
    assert dev_section.index("for step in DEV_JUMP_FLOW_ORDER") < bullets_end
    assert dev_section.index("Meals filled: auto") < dev_section.index('label="Pre-build grocery"')
    assert dev_section.index('label="Pre-build grocery"') < dev_section.index(
        'label="Per-recipe review"'
    )
    assert dev_section.index('label="Per-recipe review"') < dev_section.index('label="Final list"')


def test_dev_mode_auto_continues_without_continue_button() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    entry = source.split("def _render_weekly_plan_entry", 1)[1].split(
        "def _invalidate_stale_grocery_result", 1
    )[0]
    assert 'if choice == "dev":' in entry
    assert "plan_meal_count = 1" in entry
    assert entry.index('if choice == "dev":') < entry.index("weekly_plan_mode_continue")


def test_dev_mode_default_meal_count() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert '_weekly_plan_mode() == "dev"' in source
    assert 'key="plan_meal_count"' in source


def test_prebuild_recipe_picker_before_build_my_plan() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert "_render_prebuild_recipe_picker" in source
    assert 'key="plan_prebuild_pinned_recipes"' in source
    build_idx = source.index('if st.button("Build my plan"')
    picker_idx = source.index("_render_prebuild_recipe_picker(")
    assert picker_idx < build_idx
    assert "plan_prebuild_pinned_recipes" in source.split("def _locked_recipes_for_plan_build", 1)[1]


def test_grocery_list_extra_items_before_create_button() -> None:
    """Issue #121 / #131: Extra items in their own expander before Create grocery list."""
    source = APP_PATH.read_text(encoding="utf-8")
    section = source.split("### 2. Grocery list", 1)[1].split("def _render_grocery_result", 1)[0]

    create_idx = section.index('if st.button("Create grocery list"')
    assert 'with st.expander("Pantry & Recurring Items"' in section
    assert 'with st.expander("Add extra items"' in section
    extras_block = section.split('with st.expander("Add extra items"', 1)[1].split(
        'if st.button("Create grocery list"', 1
    )[0]
    assert "_grocery_pre_extra_items_widget_key()" in extras_block
    assert section.index('with st.expander("Add extra items"') < create_idx
    pantry_block = section.split('with st.expander("Pantry & Recurring Items"', 1)[1].split(
        'with st.expander("Add extra items"', 1
    )[0]
    assert "_grocery_pre_extra_items_widget_key()" not in pantry_block
