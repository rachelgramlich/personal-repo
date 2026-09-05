"""Tests for the shared line-item strip / parse helpers."""

from __future__ import annotations

import pytest

from src.grocery_wizard.shopping.line_items import parse_line_items, strip_line_item


class TestStripLineItem:
    def test_plain_item_unchanged(self) -> None:
        assert strip_line_item("Sugar") == "Sugar"

    def test_leading_dash(self) -> None:
        assert strip_line_item("- Flowers") == "Flowers"

    def test_leading_asterisk(self) -> None:
        assert strip_line_item("* Bread") == "Bread"

    def test_leading_bullet_char(self) -> None:
        assert strip_line_item("• Onions") == "Onions"

    def test_checklist_unchecked(self) -> None:
        assert strip_line_item("- [ ] Flowers") == "Flowers"

    def test_checklist_checked_lowercase_x(self) -> None:
        assert strip_line_item("- [x] Milk") == "Milk"

    def test_checklist_checked_uppercase_x(self) -> None:
        assert strip_line_item("- [X] Eggs") == "Eggs"

    def test_checklist_no_leading_dash(self) -> None:
        assert strip_line_item("[ ] Eggs") == "Eggs"

    def test_checklist_no_leading_dash_checked(self) -> None:
        assert strip_line_item("[x] Milk") == "Milk"

    def test_surrounding_whitespace_stripped(self) -> None:
        assert strip_line_item("  - [ ] Butter  ") == "Butter"

    def test_empty_string(self) -> None:
        assert strip_line_item("") == ""

    def test_item_with_spaces_inside_preserved(self) -> None:
        assert strip_line_item("- [ ] Brown sugar") == "Brown sugar"


class TestParseLineItems:
    def test_basic_multiline(self) -> None:
        text = "milk\neggs\nbread"
        assert parse_line_items(text) == ["milk", "eggs", "bread"]

    def test_blank_lines_ignored(self) -> None:
        text = "milk\n\neggs\n\n"
        assert parse_line_items(text) == ["milk", "eggs"]

    def test_comment_lines_ignored(self) -> None:
        text = "# heading\nmilk\n# another comment\neggs"
        assert parse_line_items(text) == ["milk", "eggs"]

    def test_strips_checklist_syntax(self) -> None:
        text = "- [ ] Flowers\n- [x] Milk\n[ ] Eggs\n- Sugar"
        assert parse_line_items(text) == ["Flowers", "Milk", "Eggs", "Sugar"]

    def test_strips_bullet_prefixes(self) -> None:
        text = "- Apples\n* Pears\n• Bananas"
        assert parse_line_items(text) == ["Apples", "Pears", "Bananas"]

    def test_empty_string_returns_empty_list(self) -> None:
        assert parse_line_items("") == []

    def test_only_blanks_and_comments(self) -> None:
        assert parse_line_items("# comment\n\n# another") == []

    def test_item_that_becomes_empty_after_strip_excluded(self) -> None:
        # A line that is just a dash with nothing after it should be skipped.
        text = "-\nmilk"
        result = parse_line_items(text)
        assert "milk" in result
        assert "" not in result

    def test_notion_paste_example(self) -> None:
        """Simulate pasting a Notion checklist block."""
        text = "- [ ] Flowers\n- [ ] Butter\n- [x] Bread"
        assert parse_line_items(text) == ["Flowers", "Butter", "Bread"]
