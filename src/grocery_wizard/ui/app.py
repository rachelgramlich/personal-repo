"""Streamlit UI for Grocery Wizard."""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit executes this file as a script; add repo root so `src.*` imports work.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from src.grocery_wizard.ui.db_access import get_db
from src.grocery_wizard.ui.notion_cache import (
    invalidate_notion_cache,
    last_recipe_cache_load_seconds,
)
from src.grocery_wizard.ui.sections.add_recipe import render_add_recipe
from src.grocery_wizard.ui.sections.pantry_recurring import render_pantry_and_recurring
from src.grocery_wizard.ui.sections.weekly_plan import render_create_weekly_plan
from src.grocery_wizard.ui.styles import inject_app_styles
from src.grocery_wizard.ui.tabs import _TAB_ADD, _TAB_WEEKLY, _UI_TABS

# Re-export for tests and AppTest entry points that import from app.
__all__ = [
    "get_db",
    "main",
    "render_add_recipe",
    "render_create_weekly_plan",
    "render_pantry_and_recurring",
]


def _render_notion_cache_controls() -> None:
    hint_col, refresh_col = st.columns([3, 2])
    with hint_col:
        load_seconds = last_recipe_cache_load_seconds()
        if load_seconds is not None:
            st.caption(f"Last full recipe load from Notion: {load_seconds:.2f}s")
    with refresh_col:
        if st.button(
            "Refresh from Notion",
            key="notion_cache_refresh",
            type="secondary",
            use_container_width=True,
            help="Reload recipes, pantry, and saved plans from Notion",
        ):
            invalidate_notion_cache()
            st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Grocery Wizard",
        page_icon="🛒",
        layout="centered",
    )
    inject_app_styles()
    st.title("Grocery Wizard")
    _render_notion_cache_controls()

    active_tab = st.segmented_control(
        "Section",
        _UI_TABS,
        default=_TAB_WEEKLY,
        key="gw_active_tab",
        label_visibility="collapsed",
    )

    if active_tab == _TAB_WEEKLY:
        render_create_weekly_plan()
    elif active_tab == _TAB_ADD:
        render_add_recipe()
    else:
        render_pantry_and_recurring()


if __name__ == "__main__":
    main()
