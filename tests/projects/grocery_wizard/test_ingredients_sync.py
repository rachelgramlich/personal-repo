"""Tests for ingredients sync merge logic and removal directives."""

from __future__ import annotations

import pytest

from projects.grocery_wizard.ingredients_sync import (
    apply_removals,
    is_directive,
    is_removal_directive,
    merge_ingredients,
    parse_ingredients_text,
    parse_removal_target,
    recipe_needs_merge,
    recipe_needs_sync,
    refresh_ingredients_for_recipe,
    split_ingredients_text,
)
from projects.grocery_wizard.notion import Recipe


def _recipe(name: str, link: str | None, ingredients: str | None) -> Recipe:
    return Recipe(
        page_id=f"id-{name}",
        name=name,
        link=link,
        ingredients=ingredients,
        properties={},
    )


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("remove: salt", True),
        ("remove salt", True),
        ("REMOVE olive oil", True),
        ("- salt", True),
        ("2 cups flour", False),
        ("kosher salt", False),
    ],
)
def test_is_removal_directive(line: str, expected: bool) -> None:
    assert is_removal_directive(line) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("remove: salt", "salt"),
        ("remove salt", "salt"),
        ("REMOVE olive oil", "olive oil"),
        ("- garlic", "garlic"),
    ],
)
def test_parse_removal_target(line: str, expected: str) -> None:
    assert parse_removal_target(line) == expected


def test_parse_ingredients_text_splits_ingredients_and_removals() -> None:
    text = "2 tbsp olive oil\n1 lb chicken\nremove: salt\n- garlic\n# pantry note\nfresh basil"
    ingredients, removals = parse_ingredients_text(text)
    assert ingredients == ["2 tbsp olive oil", "1 lb chicken", "fresh basil"]
    assert removals == ["salt", "garlic"]


def test_is_directive() -> None:
    assert is_directive("remove: pepper")
    assert is_directive("# comment")
    assert not is_directive("2 cups rice")


def test_merge_keeps_notion_additions_not_in_scrape() -> None:
    existing = "2 tbsp olive oil\n1 lb chicken\nfresh basil"
    scraped = "2 tbsp olive oil\n3 cloves garlic\n1 lb chicken breast"
    merged = merge_ingredients(existing, scraped)
    lines = [line for line in merged.splitlines() if line.strip()]
    assert "fresh basil" in lines
    assert any("garlic" in line for line in lines)
    assert any("chicken" in line for line in lines)


def test_merge_dedupes_by_normalized_name() -> None:
    existing = "2 tablespoons olive oil"
    scraped = "3 tbsp olive oil, plus more for drizzling"
    merged = merge_ingredients(existing, scraped)
    olive_lines = [line for line in merged.splitlines() if "olive" in line.lower()]
    assert len(olive_lines) == 1


def test_merge_applies_removal_directives() -> None:
    existing = "2 tbsp olive oil\nkosher salt\nremove: salt\n1 lb chicken"
    scraped = "2 tbsp olive oil\nkosher salt\n3 cloves garlic\n1 lb chicken"
    merged = merge_ingredients(existing, scraped)
    lines = [line.lower() for line in merged.splitlines() if line.strip()]
    assert not any("salt" in line for line in lines)
    assert any("garlic" in line for line in lines)


def test_apply_removals_substring_match() -> None:
    lines = ["kosher salt", "2 tbsp olive oil", "1 lb chicken"]
    result = apply_removals(lines, ["salt"])
    assert result == ["2 tbsp olive oil", "1 lb chicken"]


def test_recipe_needs_sync_empty_only() -> None:
    empty = _recipe("Empty", "https://example.com", None)
    populated = _recipe("Full", "https://example.com", "2 eggs")
    no_link = _recipe("NoLink", None, None)

    assert recipe_needs_sync(empty)
    assert recipe_needs_sync(empty, force=True)
    assert not recipe_needs_sync(populated)
    assert not recipe_needs_sync(populated, force=True)
    assert not recipe_needs_sync(no_link)


def test_recipe_needs_merge_populated_only() -> None:
    empty = _recipe("Empty", "https://example.com", None)
    populated = _recipe("Full", "https://example.com", "2 eggs")

    assert recipe_needs_merge(populated)
    assert not recipe_needs_merge(empty)


def test_split_ingredients_text_preserves_directives() -> None:
    text = "Naan bread and rice\nremove: salt\n# pantry note"
    result = split_ingredients_text(text)
    lines = result.splitlines()
    assert lines[0] == "Naan bread"
    assert lines[1] == "rice"
    assert lines[2] == "remove: salt"
    assert lines[3] == "# pantry note"


def test_refresh_ingredients_split_only(monkeypatch: pytest.MonkeyPatch) -> None:
    recipe = _recipe(
        "Curry",
        "https://example.com/curry",
        "Naan bread and rice",
    )
    updates: list[dict[str, str]] = []

    class FakeDB:
        schema = type("Schema", (), {"ingredients_column": "Ingredients"})()

        def update_recipe(self, page_id: str, field_values: dict[str, str]) -> Recipe:
            updates.append(field_values)
            return recipe

    result = refresh_ingredients_for_recipe(FakeDB(), recipe, split_only=True)
    assert result.status == "updated"
    assert result.ingredient_count == 2
    assert updates == [{"Ingredients": "Naan bread\nrice"}]


def test_refresh_ingredients_skips_without_link(monkeypatch: pytest.MonkeyPatch) -> None:
    recipe = _recipe("Manual", None, "2 eggs")

    class FakeDB:
        schema = type("Schema", (), {"ingredients_column": "Ingredients"})()

    result = refresh_ingredients_for_recipe(FakeDB(), recipe)
    assert result.status == "skipped"
    assert result.message == "no link"
