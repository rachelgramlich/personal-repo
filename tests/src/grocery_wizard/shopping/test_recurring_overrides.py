"""Tests for recurring weekly session overrides."""

from __future__ import annotations

from pathlib import Path

from src.grocery_wizard.shopping.recurring_weekly_items import (
    append_recurring_weekly_item,
    apply_recurring_session_overrides,
    remove_recurring_weekly_item,
)


def test_apply_recurring_session_overrides_add_and_remove() -> None:
    template = ["milk", "eggs", "bread"]
    result = apply_recurring_session_overrides(
        template,
        additions=["butter"],
        removals={"eggs"},
    )
    assert result == ["milk", "bread", "butter"]


def test_append_and_remove_recurring_weekly_item(tmp_path: Path) -> None:
    path = tmp_path / "recurring.txt"
    assert append_recurring_weekly_item("apples", path=path)
    assert append_recurring_weekly_item("apples", path=path) is False
    assert remove_recurring_weekly_item("apples", path=path)
    assert remove_recurring_weekly_item("apples", path=path) is False
