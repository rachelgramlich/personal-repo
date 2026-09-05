"""Regression tests for issue #29 weekly plan swap UI in app.py."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_weekly_plan_build_shows_per_meal_swap_and_edit_manually() -> None:
    """AppTest smoke test: Build my plan renders per-meal ↺ buttons and simplified expander."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_FILE, default_timeout=60)
    at.run(timeout=60)

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
