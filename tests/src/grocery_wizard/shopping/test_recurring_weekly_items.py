"""Tests for recurring weekly grocery items config and prompts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.grocery_wizard.shopping.recurring_weekly_items import (
    load_recurring_weekly_items,
    prompt_recurring_weekly_items,
    write_recurring_weekly_items,
)


def test_load_recurring_weekly_items_skips_comments_and_blanks(tmp_path: Path) -> None:
    path = tmp_path / "recurring_weekly_items.txt"
    path.write_text("# comment\nberries\n\nbananas\n", encoding="utf-8")

    assert load_recurring_weekly_items(path) == ["berries", "bananas"]


def test_load_recurring_weekly_items_strips_checklist_prefixes(tmp_path: Path) -> None:
    path = tmp_path / "recurring_weekly_items.txt"
    path.write_text("- [ ] berries\n- [x] milk\n[ ] bananas\n", encoding="utf-8")

    assert load_recurring_weekly_items(path) == ["berries", "milk", "bananas"]


def test_write_recurring_weekly_items_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "recurring_weekly_items.txt"
    write_recurring_weekly_items(path, ["berries", "milk"])

    assert load_recurring_weekly_items(path) == ["berries", "milk"]
    assert path.read_text(encoding="utf-8").endswith("milk\n")


def test_prompt_recurring_weekly_items_accepts_defaults() -> None:
    with patch("builtins.input", return_value=""):
        assert prompt_recurring_weekly_items(["berries", "milk"], interactive=True) == [
            "berries",
            "milk",
        ]


def test_prompt_recurring_weekly_items_skip_returns_empty() -> None:
    with patch("builtins.input", return_value="skip"):
        assert prompt_recurring_weekly_items(["berries"], interactive=True) == []


def test_prompt_recurring_weekly_items_edit_and_save(tmp_path: Path) -> None:
    path = tmp_path / "recurring_weekly_items.txt"
    inputs = iter(["edit", "yogurt", "", "y", ""])
    with patch("builtins.input", side_effect=inputs):
        result = prompt_recurring_weekly_items(["berries"], path=path, interactive=True)

    assert result == ["yogurt"]
    assert load_recurring_weekly_items(path) == ["yogurt"]


def test_prompt_recurring_weekly_items_edit_strips_checklist_syntax() -> None:
    inputs = iter(["edit", "- [ ] yogurt", "- [x] milk", "", "", ""])
    with patch("builtins.input", side_effect=inputs):
        result = prompt_recurring_weekly_items(["berries"], interactive=True)

    assert result == ["yogurt", "milk"]


def test_prompt_recurring_weekly_items_edit_can_clear_list() -> None:
    with patch("builtins.input", side_effect=["edit", "", "", ""]):
        result = prompt_recurring_weekly_items(["berries", "milk"], interactive=True)

    assert result == []
