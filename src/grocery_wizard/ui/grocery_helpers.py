"""Shared grocery-list helpers for Streamlit sections."""

from __future__ import annotations

import streamlit as st

from src.grocery_wizard.integrations.notion import Recipe
from src.grocery_wizard.shopping.grocery_list import merge_grocery_items
from src.grocery_wizard.shopping.line_items import parse_line_items


def meal_entries_with_links(
    meal_names: list[str],
    recipes: list[Recipe],
) -> list[tuple[str, str | None]]:
    recipes_by_name = {recipe.name.lower(): recipe for recipe in recipes}
    entries: list[tuple[str, str | None]] = []
    for name in meal_names:
        recipe = recipes_by_name.get(name.lower())
        link = recipe.link if recipe else None
        entries.append((name, link))
    return entries


def render_copy_download(
    text: str,
    *,
    label: str = "Copy list",
    key: str,
    file_name: str,
) -> None:
    """Download plain text instead of an iframe clipboard widget (lighter DOM)."""
    st.download_button(
        label=label,
        data=text.encode("utf-8"),
        file_name=file_name,
        mime="text/plain",
        key=key,
        use_container_width=True,
    )
    st.caption("Select-all in the text area above, or use Download for the same text.")


def parse_line_items_text(text: str) -> list[str]:
    return parse_line_items(text)


def compute_grocery_drafts(
    items: list[str],
    readd: list[str],
    additional_text: str,
    *,
    run_removals: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    draft_items = merge_grocery_items(items, readd)
    final_items = merge_grocery_items(items, readd, parse_line_items_text(additional_text))
    if run_removals:
        final_items = apply_run_removals(final_items, run_removals)
    return draft_items, final_items


def apply_run_removals(items: list[str], removals: set[str]) -> list[str]:
    if not removals:
        return items
    keys = {name.strip().lower() for name in removals if name.strip()}
    filtered: list[str] = []
    for line in items:
        lowered = line.strip().lower()
        if any(key in lowered or lowered in key for key in keys):
            continue
        filtered.append(line)
    return filtered


def grocery_line_matches_name(line: str, name: str) -> bool:
    lowered_line = line.strip().lower()
    lowered_name = name.strip().lower()
    if not lowered_line or not lowered_name:
        return False
    return lowered_name in lowered_line or lowered_line in lowered_name
