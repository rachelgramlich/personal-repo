"""Pantry staples and recurring weekly template tab."""

from __future__ import annotations

import html
from collections.abc import Callable

import streamlit as st

from src.grocery_wizard.config import load_config
from src.grocery_wizard.shopping.pantry import append_pantry_item, remove_pantry_item_by_name
from src.grocery_wizard.shopping.recurring_weekly_items import (
    append_recurring_weekly_item,
    load_recurring_weekly_items,
    remove_recurring_weekly_item,
)
from src.grocery_wizard.shopping.store_aisles import (
    StoreAisleConfig,
    aisle_label,
    classify_aisle,
    load_store_aisles,
)
from src.grocery_wizard.ui.notion_cache import cached_pantry_entries, invalidate_notion_cache


def _load_pantry_entries_from_notion() -> list:
    config = load_config()
    return cached_pantry_entries(pantry_database_id=config.notion_pantry_database_id)


def _remove_pantry_item_and_invalidate(name: str) -> bool:
    if remove_pantry_item_by_name(name):
        invalidate_notion_cache()
        return True
    return False


def _pantry_display_aisle_label(entry: object, *, config: StoreAisleConfig) -> str:
    stored = str(getattr(entry, "section", None) or "").strip()
    if stored:
        return stored
    aisle_id = classify_aisle(str(getattr(entry, "name", "")), config=config)
    return aisle_label(aisle_id, config=config)


def _group_pantry_items_by_store_aisle(
    entries: list,
    *,
    config: StoreAisleConfig,
) -> list[tuple[str, list[str]]]:
    by_label: dict[str, list[str]] = {}
    for entry in entries:
        label = _pantry_display_aisle_label(entry, config=config)
        by_label.setdefault(label, []).append(str(getattr(entry, "name", "")))

    walk_order = [aisle_label(aisle_id, config=config) for aisle_id in config.aisle_order]
    rank = {label.lower(): index for index, label in enumerate(walk_order)}

    grouped: list[tuple[str, list[str]]] = []
    def _aisle_sort_key(text: str) -> tuple[int, str]:
        return rank.get(text.lower(), 999), text.lower()

    for label in sorted(by_label.keys(), key=_aisle_sort_key):
        names = sorted(set(by_label[label]), key=str.lower)
        grouped.append((label, names))
    return grouped


def _render_markdown_item_list(items: list[str], *, item_class: str) -> None:
    if not items:
        return
    lines = [
        f'<li class="{item_class}">{html.escape(name)}</li>' for name in items
    ]
    st.markdown(
        f'<ul class="gw-item-list">{"".join(lines)}</ul>',
        unsafe_allow_html=True,
    )


def _render_remove_picker(
    *,
    items: list[str],
    key: str,
    label: str,
    on_remove: Callable[[str], bool],
) -> None:
    if not items:
        return
    pick = st.selectbox(
        label,
        options=["", *items],
        format_func=lambda name: name or "Choose an item…",
        key=key,
        label_visibility="visible",
    )
    if st.button("Remove selected", key=f"{key}_btn", type="secondary"):
        if not pick:
            st.warning("Choose an item to remove.")
        elif on_remove(pick):
            st.rerun()
        else:
            st.warning(f"Could not remove “{pick}”.")


def render_pantry_and_recurring() -> None:
    st.subheader("Pantry & recurring items")
    st.caption(
        "Recurring items are added to every new weekly list. "
        "Pantry items are assumed on hand when building grocery lists."
    )

    st.markdown("### Recurring weekly items")
    template = load_recurring_weekly_items()
    if template:
        _render_markdown_item_list(template, item_class="gw-recurring-item")
        _render_remove_picker(
            items=template,
            key="recurring_tab_remove_pick",
            label="Remove a recurring item",
            on_remove=remove_recurring_weekly_item,
        )
    else:
        st.caption("_No recurring items yet._")

    with st.form("recurring_add_form", clear_on_submit=True):
        new_recurring = st.text_input("Add recurring item", placeholder="e.g. berries")
        if st.form_submit_button("Add recurring item"):
            name = new_recurring.strip()
            if not name:
                st.warning("Enter an item name.")
            elif append_recurring_weekly_item(name):
                st.success(f"Added “{name}” to recurring items.")
                st.rerun()
            else:
                st.warning("Could not add — empty name or already on the list.")

    st.divider()
    st.markdown("### Pantry")
    st.caption("Grouped by the same store aisles as your grocery list (`config/store_aisles.txt`).")
    aisle_config = load_store_aisles()
    try:
        pantry_entries = _load_pantry_entries_from_notion()
    except ValueError as exc:
        st.error(str(exc))
        pantry_entries = []

    grouped_aisles = _group_pantry_items_by_store_aisle(pantry_entries, config=aisle_config)
    all_pantry_names: list[str] = []
    if grouped_aisles:
        for aisle_heading, items in grouped_aisles:
            safe_heading = html.escape(aisle_heading)
            st.markdown(
                f'<p class="gw-pantry-aisle-heading">{safe_heading}</p>',
                unsafe_allow_html=True,
            )
            _render_markdown_item_list(items, item_class="gw-pantry-item")
            all_pantry_names.extend(items)
    elif pantry_entries:
        st.caption("No pantry items matched a store aisle.")
    else:
        st.caption("No pantry items yet.")

    if all_pantry_names:
        _render_remove_picker(
            items=sorted(set(all_pantry_names), key=str.lower),
            key="pantry_tab_remove_pick",
            label="Remove a pantry item",
            on_remove=_remove_pantry_item_and_invalidate,
        )

    with st.form("pantry_add_form", clear_on_submit=True):
        new_pantry_name = st.text_input("Add pantry item", placeholder="e.g. soy sauce")
        new_pantry_aisle = st.selectbox(
            "Store aisle",
            options=list(aisle_config.aisle_order),
            format_func=lambda aisle_id: aisle_label(aisle_id, config=aisle_config),
            index=list(aisle_config.aisle_order).index("dry goods")
            if "dry goods" in aisle_config.aisle_order
            else 0,
        )
        if st.form_submit_button("Add to pantry", type="primary"):
            name = new_pantry_name.strip()
            if not name:
                st.warning("Enter an item name.")
            else:
                section_label = aisle_label(new_pantry_aisle, config=aisle_config)
                if append_pantry_item(name, section=section_label):
                    invalidate_notion_cache()
                    st.success(f"Added “{name}” to pantry ({section_label}).")
                    st.rerun()
                else:
                    st.warning("Could not add — empty name or already in pantry.")
