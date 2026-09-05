"""Tests that extra grocery items do not modify recurring weekly items config."""

from __future__ import annotations

from pathlib import Path

from src.grocery_wizard.shopping.recurring_weekly_items import (
    load_recurring_weekly_items,
    write_recurring_weekly_items,
)
from src.grocery_wizard.ui.app import _persist_recurring_if_edited


def test_persist_recurring_if_edited_skips_when_only_extras_would_change(tmp_path: Path) -> None:
    """Adding one-week extras must not rewrite recurring_weekly_items.txt."""
    path = tmp_path / "recurring_weekly_items.txt"
    write_recurring_weekly_items(path, ["berries", "milk"])

    default_recurring = load_recurring_weekly_items(path)
    recurring_text = "\n".join(default_recurring)
    extra_items_text = "flowers\n- [ ] Paper towels"

    _persist_recurring_if_edited(recurring_text, default_recurring, path=path)

    assert load_recurring_weekly_items(path) == ["berries", "milk"]
    assert extra_items_text  # extras are unrelated to recurring persistence


def test_persist_recurring_if_edited_skips_checklist_normalization_only(tmp_path: Path) -> None:
    """Checklist formatting differences alone must not trigger a save."""
    path = tmp_path / "recurring_weekly_items.txt"
    path.write_text("- [ ] Bananas\nmilk\n", encoding="utf-8")

    default_recurring = load_recurring_weekly_items(path)
    recurring_text = "\n".join(default_recurring)

    _persist_recurring_if_edited(recurring_text, default_recurring, path=path)

    assert path.read_text(encoding="utf-8") == "- [ ] Bananas\nmilk\n"


def test_persist_recurring_if_edited_saves_dedicated_field_changes(tmp_path: Path) -> None:
    """Recurring weekly items save only when the dedicated field is edited."""
    path = tmp_path / "recurring_weekly_items.txt"
    write_recurring_weekly_items(path, ["berries", "milk"])

    default_recurring = load_recurring_weekly_items(path)
    recurring_text = "berries\nmilk\nyogurt"

    _persist_recurring_if_edited(recurring_text, default_recurring, path=path)

    assert load_recurring_weekly_items(path) == ["berries", "milk", "yogurt"]
