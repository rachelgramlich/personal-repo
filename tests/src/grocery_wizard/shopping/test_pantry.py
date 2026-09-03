"""Tests for pantry file parsing and display."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.grocery_wizard.config import PANTRY_PATH
from src.grocery_wizard.shopping.pantry import (
    _matches_pantry_search,
    format_pantry_display,
    is_pantry_item,
    load_pantry,
    parse_pantry_file,
    write_pantry_file,
)


def test_load_pantry_ignores_comments_and_headers(tmp_path: Path) -> None:
    path = tmp_path / "pantry.txt"
    path.write_text(
        "# header\nsalt\n# --- section ---\npepper\n",
        encoding="utf-8",
    )
    assert load_pantry(path) == {"salt", "pepper"}


def test_default_pantry_path_is_committed_config() -> None:
    assert PANTRY_PATH.name == "pantry.txt"
    assert PANTRY_PATH.parent.name == "config"
    assert PANTRY_PATH.exists()
    assert "salt" in load_pantry()


def test_parse_pantry_file_groups_by_section_headers(tmp_path: Path) -> None:
    path = tmp_path / "pantry.txt"
    path.write_text(
        "# --- Spices ---\ncumin\npaprika\n# --- Oils ---\nolive oil\n",
        encoding="utf-8",
    )
    lines, sections = parse_pantry_file(path)
    assert len(sections) == 2
    assert sections[0].header == "# --- Spices ---"
    assert [item for _idx, item in sections[0].items] == ["cumin", "paprika"]
    assert sections[1].header == "# --- Oils ---"
    assert [item for _idx, item in sections[1].items] == ["olive oil"]
    assert len(lines) == 5


def test_format_pantry_display_numbered(tmp_path: Path) -> None:
    path = tmp_path / "pantry.txt"
    path.write_text("# --- Spices ---\ncumin\n", encoding="utf-8")
    _lines, sections = parse_pantry_file(path)
    display = format_pantry_display(sections)
    assert "# --- Spices ---" in display
    assert "  1. cumin" in display


def test_write_pantry_file_adds_trailing_newline(tmp_path: Path) -> None:
    path = tmp_path / "pantry.txt"
    write_pantry_file(path, ["salt", "pepper"])
    assert path.read_text(encoding="utf-8") == "salt\npepper\n"


@pytest.mark.parametrize(
    ("ingredient", "expected"),
    [
        ("kosher salt", True),
        ("olive oil", True),
        ("beef", False),
        ("ground beef", False),
        ("white beans", False),
        ("rice", True),
        ("brown rice", True),
    ],
)
def test_is_pantry_item_phrase_matching(ingredient: str, expected: bool) -> None:
    pantry = {"salt", "olive oil", "beef stock", "rice", "white wine vinegar"}
    assert is_pantry_item(ingredient, pantry) is expected


@pytest.mark.parametrize(
    ("search", "item", "expected"),
    [
        ("salt", "salt", True),
        ("beef stock", "beef stock", True),
        ("beef", "beef stock", True),
        ("stock", "beef stock", True),
        ("low sodium beef stock", "beef stock", True),
        ("ice", "rice", False),
        ("vinegar", "white wine vinegar", True),
        ("wine", "white wine vinegar", True),
    ],
)
def test_matches_pantry_search(search: str, item: str, expected: bool) -> None:
    assert _matches_pantry_search(search, item) is expected
