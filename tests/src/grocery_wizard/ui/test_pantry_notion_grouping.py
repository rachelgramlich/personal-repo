"""Tests for pantry UI grouping from Notion Store Aisle values."""

from __future__ import annotations

from dataclasses import dataclass

from src.grocery_wizard.shopping.store_aisles import load_store_aisles
from src.grocery_wizard.ui.sections.pantry_recurring import (
    _group_pantry_items_by_store_aisle,
    _pantry_display_aisle_label,
)


@dataclass
class _Entry:
    name: str
    section: str | None


def test_pantry_display_uses_exact_notion_aisle_label() -> None:
    config = load_store_aisles()
    entry = _Entry(name="bananas", section="Baking")
    assert _pantry_display_aisle_label(entry, config=config) == "Baking"


def test_pantry_groups_under_notion_label_not_classifier() -> None:
    config = load_store_aisles()
    entries = [_Entry(name="bananas", section="Baking")]
    grouped = _group_pantry_items_by_store_aisle(entries, config=config)
    assert grouped[0][0] == "Baking"
    assert grouped[0][1][0] == "bananas"
