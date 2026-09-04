"""Tests for perpetual grocery items config and prompts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.grocery_wizard.shopping.perpetual_items import (
    load_perpetual_items,
    prompt_perpetual_items,
    write_perpetual_items,
)


def test_load_perpetual_items_skips_comments_and_blanks(tmp_path: Path) -> None:
    path = tmp_path / "perpetual_items.txt"
    path.write_text("# comment\nberries\n\nbananas\n", encoding="utf-8")

    assert load_perpetual_items(path) == ["berries", "bananas"]


def test_write_perpetual_items_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "perpetual_items.txt"
    write_perpetual_items(path, ["berries", "milk"])

    assert load_perpetual_items(path) == ["berries", "milk"]
    assert path.read_text(encoding="utf-8").endswith("milk\n")


def test_prompt_perpetual_items_accepts_defaults() -> None:
    with patch("builtins.input", return_value=""):
        assert prompt_perpetual_items(["berries", "milk"], interactive=True) == [
            "berries",
            "milk",
        ]


def test_prompt_perpetual_items_skip_returns_empty() -> None:
    with patch("builtins.input", return_value="skip"):
        assert prompt_perpetual_items(["berries"], interactive=True) == []


def test_prompt_perpetual_items_edit_and_save(tmp_path: Path) -> None:
    path = tmp_path / "perpetual_items.txt"
    inputs = iter(["edit", "yogurt", "", "y", ""])
    with patch("builtins.input", side_effect=inputs):
        result = prompt_perpetual_items(["berries"], path=path, interactive=True)

    assert result == ["yogurt"]
    assert load_perpetual_items(path) == ["yogurt"]
