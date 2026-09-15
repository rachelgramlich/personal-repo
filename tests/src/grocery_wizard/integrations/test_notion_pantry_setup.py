"""Tests for pantry Notion section sync helpers."""

from __future__ import annotations

from src.grocery_wizard.integrations.notion_pantry_setup import _merge_select_option_payloads


def test_merge_select_options_preserves_existing_ids() -> None:
    existing = {
        "type": "select",
        "select": {
            "options": [
                {"id": "abc", "name": "Fruit", "color": "red"},
                {"id": "def", "name": "Other", "color": "gray"},
            ]
        },
    }
    merged = _merge_select_option_payloads(existing, ["Fruit", "Vegetables", "Other"])
    by_name = {item["name"]: item for item in merged}
    assert by_name["Fruit"] == {"id": "abc", "name": "Fruit"}
    assert by_name["Other"] == {"id": "def", "name": "Other"}
    assert by_name["Vegetables"]["name"] == "Vegetables"
    assert "id" not in by_name["Vegetables"]
