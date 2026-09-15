"""Streamlit ``st.cache_data`` wrappers for Notion reads with explicit invalidation."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import streamlit as st

from src.grocery_wizard.integrations.notion import NotionRecipesDB, Recipe
from src.grocery_wizard.planning.saved_weekly_plans import SavedWeeklyPlan, list_saved_plans

if TYPE_CHECKING:
    from src.grocery_wizard.integrations.notion_household import PantryEntry

_GENERATION_KEY = "notion_cache_generation"
_LAST_RECIPE_LOAD_KEY = "_notion_cache_last_recipe_load_s"


def notion_cache_generation() -> int:
    if _GENERATION_KEY not in st.session_state:
        st.session_state[_GENERATION_KEY] = 0
    return int(st.session_state[_GENERATION_KEY])


def invalidate_notion_cache() -> None:
    """Drop cached Notion reads after a write or when the user requests refresh."""
    st.session_state[_GENERATION_KEY] = notion_cache_generation() + 1
    st.cache_data.clear()


def last_recipe_cache_load_seconds() -> float | None:
    """Seconds for the most recent cached recipe load (cache miss only)."""
    value = st.session_state.get(_LAST_RECIPE_LOAD_KEY)
    return float(value) if value is not None else None


@st.cache_data(show_spinner=False)
def _load_recipes_cached(database_id: str, generation: int, _db: NotionRecipesDB) -> list[Recipe]:
    del database_id, generation
    return _db.query_recipes()


@st.cache_data(show_spinner=False)
def _load_pantry_cached(generation: int, _household_db_id: str) -> list[PantryEntry]:
    del generation
    from src.grocery_wizard.integrations.notion_household import NotionPantryDB

    return NotionPantryDB().list_entries()


@st.cache_data(show_spinner=False)
def _load_saved_plans_cached(
    weekly_plans_database_id: str,
    generation: int,
    _recipes_db: NotionRecipesDB,
) -> list[SavedWeeklyPlan]:
    del generation
    del weekly_plans_database_id
    return list_saved_plans(recipes_db=_recipes_db)


def cached_query_recipes(db: NotionRecipesDB) -> list[Recipe]:
    t0 = time.perf_counter()
    recipes = _load_recipes_cached(db._database_id, notion_cache_generation(), db)
    elapsed = time.perf_counter() - t0
    if elapsed >= 0.05:
        st.session_state[_LAST_RECIPE_LOAD_KEY] = elapsed
    return recipes


def cached_pantry_entries(*, pantry_database_id: str) -> list[PantryEntry]:
    return _load_pantry_cached(notion_cache_generation(), pantry_database_id)


def cached_saved_plans(
    db: NotionRecipesDB,
    *,
    weekly_plans_database_id: str,
) -> list[SavedWeeklyPlan]:
    return _load_saved_plans_cached(
        weekly_plans_database_id,
        notion_cache_generation(),
        db,
    )
