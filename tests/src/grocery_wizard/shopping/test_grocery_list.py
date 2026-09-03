"""Tests for grocery list pantry exclusion and sync ingredient persistence."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.grocery_wizard.ingredients.sync import sync_ingredients_for_recipe
from src.grocery_wizard.integrations.notion import Recipe
from src.grocery_wizard.shopping.grocery_list import (
    _print_excluded_summary,
    _recipes_needing_backfill,
    build_grocery_list,
    match_excluded_items,
    parse_readd_excluded,
    run_grocery_list,
)


def _recipe(name: str, ingredients: str) -> Recipe:
    return Recipe(
        page_id=f"id-{name}",
        name=name,
        link="https://example.com/recipe",
        ingredients=ingredients,
        properties={},
    )


@pytest.fixture
def pantry_file(tmp_path: Path) -> Path:
    path = tmp_path / "pantry.txt"
    path.write_text("salt\nolive oil\ngarlic\n", encoding="utf-8")
    return path


def test_build_grocery_list_excludes_pantry_by_default(pantry_file: Path) -> None:
    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe(
            "Test Recipe",
            "2 tbsp olive oil\n3 cloves garlic\n1 lb chicken breast",
        )
    ]

    items, excluded = build_grocery_list(
        db,
        recipe_names=["Test Recipe"],
        pantry_path=pantry_file,
        exclude_pantry=True,
    )

    assert "chicken breast" in items
    assert "olive oil" not in items
    assert "garlic" not in items
    assert "olive oil" in excluded
    assert "garlic" in excluded


def test_build_grocery_list_include_pantry(pantry_file: Path) -> None:
    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe(
            "Test Recipe",
            "2 tbsp olive oil\n3 cloves garlic\n1 lb chicken breast",
        )
    ]

    items, excluded = build_grocery_list(
        db,
        recipe_names=["Test Recipe"],
        pantry_path=pantry_file,
        exclude_pantry=False,
    )

    assert "chicken breast" in items
    assert "olive oil" in items
    assert "garlic" in items
    assert excluded == []


def test_build_grocery_list_splits_compound_ingredients(tmp_path: Path) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("rice\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe(
            "Chana Masala",
            "Naan bread and rice, to serve (optional)\n"
            "Chopped fresh cilantro and lime wedges, for garnish (optional)",
        )
    ]

    items, excluded = build_grocery_list(
        db,
        recipe_names=["Chana Masala"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert "naan bread" in items
    assert "cilantro" in items
    assert "limes" in items
    assert "rice" not in items
    assert "naan bread and rice" not in items
    assert "cilantro and lime wedges" not in items
    assert "rice" in excluded


@pytest.mark.parametrize(
    "ingredient_line",
    [
        "cauliflower and rice",
        "cauliflower & rice",
    ],
)
def test_build_grocery_list_splits_cauliflower_and_rice(
    tmp_path: Path,
    ingredient_line: str,
) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("rice\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Stir Fry", ingredient_line),
    ]

    items, excluded = build_grocery_list(
        db,
        recipe_names=["Stir Fry"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert "cauliflower" in items
    assert "rice" not in items
    assert "cauliflower rice" not in items
    assert "rice" in excluded


def test_build_grocery_list_keeps_cauliflower_rice_without_conjunction(tmp_path: Path) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Stir Fry", "cauliflower rice"),
    ]

    items, excluded = build_grocery_list(
        db,
        recipe_names=["Stir Fry"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert items == ["cauliflower rice"]
    assert "rice" not in excluded


def test_build_grocery_list_white_beans_not_split(tmp_path: Path) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Soup", "2 cans white beans"),
    ]

    items, excluded = build_grocery_list(
        db,
        recipe_names=["Soup"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert items == ["white beans"]
    assert "white" not in items
    assert "beans" not in items


def test_run_grocery_list_interactive_flow_order(
    pantry_file: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe(
            "Test Recipe",
            "2 tbsp olive oil\n1 lb chicken breast",
        )
    ]
    week_plan = pantry_file.parent / "week_plan.json"
    week_plan.write_text('{"recipes": ["Test Recipe"]}', encoding="utf-8")

    inputs = iter(["", "eggs", "", ""])
    with (
        patch("src.grocery_wizard.shopping.grocery_list.input", side_effect=inputs),
        patch("src.grocery_wizard.shopping.grocery_list._prompt_staples", return_value=["eggs"]),
        patch(
            "src.grocery_wizard.shopping.grocery_list._prompt_accept_or_edit",
            side_effect=lambda items: items,
        ),
    ):
        code = run_grocery_list(
            db,
            week_plan_path=week_plan,
            pantry_path=pantry_file,
        )

    assert code == 0
    output = capsys.readouterr().out
    excluded_pos = output.find("Excluded staples")
    draft_pos = output.find("Draft grocery list")
    grocery_pos = output.find("Grocery list")
    final_pos = output.find("Final grocery list")
    assert excluded_pos != -1
    assert draft_pos != -1
    assert grocery_pos != -1
    assert final_pos != -1
    assert excluded_pos < draft_pos < grocery_pos < final_pos
    assert "eggs" in output
    assert "chicken breast" in output


def test_sync_writes_full_ingredients_including_pantry() -> None:
    db = MagicMock()
    db.schema.ingredients_column = "Ingredients"
    recipe = Recipe(
        page_id="p1",
        name="Test",
        link="https://example.com/recipe",
        ingredients=None,
        properties={},
    )
    full_text = "2 tbsp olive oil\nkosher salt\n3 cloves garlic\n1 lb chicken"

    with patch(
        "src.grocery_wizard.ingredients.sync.scrape_ingredients_text",
        return_value=full_text,
    ):
        result = sync_ingredients_for_recipe(db, recipe)

    assert result.status == "synced"
    db.update_recipe.assert_called_once_with(
        "p1",
        {"Ingredients": full_text},
    )


def test_match_excluded_items_substring() -> None:
    excluded = ["garlic", "olive oil", "kosher salt"]
    assert match_excluded_items("garlic", excluded) == ["garlic"]
    assert match_excluded_items("oil", excluded) == ["olive oil"]


def test_parse_readd_excluded_by_number_and_name() -> None:
    excluded = ["garlic", "olive oil", "kosher salt"]
    assert parse_readd_excluded("1, oil", excluded) == ["garlic", "olive oil"]
    assert parse_readd_excluded("", excluded) == []


def test_print_excluded_summary_always_numbered(capsys: pytest.CaptureFixture[str]) -> None:
    _print_excluded_summary(["garlic", "olive oil"])
    output = capsys.readouterr().out
    assert "Excluded staples" in output
    assert "1. garlic" in output
    assert "2. olive oil" in output


def test_recipes_needing_backfill_detects_empty_ingredients() -> None:
    recipes_by_name = {
        "soup": _recipe("Soup", ""),
        "salad": _recipe("Salad", "lettuce"),
    }
    recipes_by_name["soup"].ingredients = None
    needs = _recipes_needing_backfill(["Soup", "Salad"], recipes_by_name)
    assert [recipe.name for recipe in needs] == ["Soup"]


def test_run_grocery_list_quiet_skips_excluded_display(
    pantry_file: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe(
            "Test Recipe",
            "2 tbsp olive oil\n1 lb chicken breast",
        )
    ]
    week_plan = pantry_file.parent / "week_plan.json"
    week_plan.write_text('{"recipes": ["Test Recipe"]}', encoding="utf-8")

    with patch("src.grocery_wizard.shopping.grocery_list._prompt_staples", return_value=[]):
        code = run_grocery_list(
            db,
            quiet=True,
            week_plan_path=week_plan,
            pantry_path=pantry_file,
        )

    assert code == 0
    output = capsys.readouterr().out
    assert "Excluded staples" not in output


def test_load_week_plan_names_falls_back_to_legacy_path(tmp_path: Path, monkeypatch) -> None:
    from src.grocery_wizard.config import LEGACY_WEEK_PLAN_PATH, WEEK_PLAN_PATH
    from src.grocery_wizard.shopping.grocery_list import _load_week_plan_names

    monkeypatch.chdir(tmp_path)
    legacy_path = tmp_path / LEGACY_WEEK_PLAN_PATH
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text('{"recipes": ["Legacy Soup"]}', encoding="utf-8")

    assert not (tmp_path / WEEK_PLAN_PATH).exists()
    assert _load_week_plan_names(WEEK_PLAN_PATH) == ["Legacy Soup"]
