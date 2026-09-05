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
    format_grocery_item,
    format_meals_and_grocery_list,
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


@pytest.mark.parametrize(
    ("name", "amount", "expected"),
    [
        ("chicken breast", "1 lb", "1 lb chicken breast"),
        ("eggs", None, "eggs"),
        ("garlic", None, "garlic"),
    ],
)
def test_format_grocery_item(name: str, amount: str | None, expected: str) -> None:
    assert format_grocery_item(name, amount) == expected


def test_format_meals_and_grocery_list_includes_both_sections() -> None:
    meals = [
        ("Chicken Tikka", "https://example.com/tikka"),
        ("Salad", None),
    ]
    grocery_items = ["onions", "chicken breast", "lettuce"]

    text = format_meals_and_grocery_list(meals, grocery_items)

    assert text == (
        "Meals\n- Chicken Tikka (https://example.com/tikka)\n- Salad\n\nGrocery List\n- lettuce\n- onions\n- chicken breast"
    )


def test_format_meals_and_grocery_list_empty_grocery_items() -> None:
    text = format_meals_and_grocery_list([("Soup", "https://example.com/soup")], [])
    assert text == ("Meals\n- Soup (https://example.com/soup)\n\nGrocery List")


def test_build_grocery_list_excludes_pantry_by_default(pantry_file: Path) -> None:
    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe(
            "Test Recipe",
            "2 tbsp olive oil\n3 cloves garlic\n1 lb chicken breast",
        )
    ]

    items, excluded, _sync, _missing = build_grocery_list(
        db,
        recipe_names=["Test Recipe"],
        pantry_path=pantry_file,
        exclude_pantry=True,
    )

    assert any("chicken breast" in item for item in items)
    assert not any("olive oil" in item for item in items)
    assert not any("garlic" in item for item in items)
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

    items, excluded, _sync, _missing = build_grocery_list(
        db,
        recipe_names=["Test Recipe"],
        pantry_path=pantry_file,
        exclude_pantry=False,
    )

    assert any("chicken breast" in item for item in items)
    assert any("olive oil" in item for item in items)
    assert any("garlic" in item for item in items)
    assert excluded == []


def test_build_grocery_list_splits_compound_ingredients(tmp_path: Path) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("rice\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe(
            "Chana Masala",
            "Naan bread\n"
            "rice, to serve (optional)\n"
            "Chopped fresh cilantro\n"
            "lime wedges, for garnish (optional)",
        )
    ]

    items, excluded, _sync, _missing = build_grocery_list(
        db,
        recipe_names=["Chana Masala"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert any(item.lower() == "naan bread" for item in items)
    assert "cilantro" in items
    assert "limes" in items
    assert "rice" not in items
    assert "naan bread and rice" not in items
    assert "cilantro and lime wedges" not in items
    assert "rice" in excluded


@pytest.mark.parametrize(
    "ingredient_text",
    [
        "cauliflower\nrice",
    ],
)
def test_build_grocery_list_splits_cauliflower_and_rice(
    tmp_path: Path,
    ingredient_text: str,
) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("rice\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Stir Fry", "cauliflower\nrice"),
    ]

    items, excluded, _sync, _missing = build_grocery_list(
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

    items, excluded, _sync, _missing = build_grocery_list(
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

    items, _excluded, _sync, _missing = build_grocery_list(
        db,
        recipe_names=["Soup"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert items == ["2 cans white beans"]
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
        patch(
            "src.grocery_wizard.shopping.grocery_list.prompt_recurring_weekly_items",
            return_value=[],
        ),
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


def test_sync_writes_prepared_ingredients() -> None:
    db = MagicMock()
    db.schema.ingredients_column = "Ingredients"
    recipe = Recipe(
        page_id="p1",
        name="Test",
        link="https://example.com/recipe",
        ingredients=None,
        properties={},
    )
    raw_text = "2 sweet potatoes and 1 red onion\nsliced into half-moons"

    with patch(
        "src.grocery_wizard.ingredients.sync.scrape_ingredients_text",
        return_value=raw_text,
    ):
        result = sync_ingredients_for_recipe(db, recipe)

    assert result.status == "synced"
    db.update_recipe.assert_called_once()
    written = db.update_recipe.call_args[0][1]["Ingredients"]
    assert "sweet potatoes" in written
    assert "red onion" in written
    assert "half-moons" not in written


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


def test_run_grocery_list_quiet_includes_recurring_weekly_items_by_default(
    pantry_file: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Test Recipe", "1 lb chicken breast"),
    ]
    week_plan = pantry_file.parent / "week_plan.json"
    week_plan.write_text('{"recipes": ["Test Recipe"]}', encoding="utf-8")

    with patch("src.grocery_wizard.shopping.grocery_list._prompt_staples", return_value=[]):
        code = run_grocery_list(
            db,
            quiet=True,
            week_plan_path=week_plan,
            pantry_path=pantry_file,
            recurring_weekly_items=["milk"],
        )

    assert code == 0
    assert "milk" in capsys.readouterr().out


def test_run_grocery_list_quiet_can_skip_recurring_weekly_items(
    pantry_file: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Test Recipe", "1 lb chicken breast"),
    ]
    week_plan = pantry_file.parent / "week_plan.json"
    week_plan.write_text('{"recipes": ["Test Recipe"]}', encoding="utf-8")

    with patch("src.grocery_wizard.shopping.grocery_list._prompt_staples", return_value=[]):
        code = run_grocery_list(
            db,
            quiet=True,
            include_recurring_weekly_items=False,
            recurring_weekly_items=["milk"],
            week_plan_path=week_plan,
            pantry_path=pantry_file,
        )

    assert code == 0
    assert "milk" not in capsys.readouterr().out


def test_load_week_plan_names_falls_back_to_legacy_path(tmp_path: Path, monkeypatch) -> None:
    from src.grocery_wizard.config import LEGACY_WEEK_PLAN_PATH, WEEK_PLAN_PATH
    from src.grocery_wizard.shopping.grocery_list import _load_week_plan_names

    monkeypatch.chdir(tmp_path)
    legacy_path = tmp_path / LEGACY_WEEK_PLAN_PATH
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text('{"recipes": ["Legacy Soup"]}', encoding="utf-8")

    assert not (tmp_path / WEEK_PLAN_PATH).exists()
    assert _load_week_plan_names(WEEK_PLAN_PATH) == ["Legacy Soup"]


def test_load_week_plan_names_invalid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from src.grocery_wizard.shopping.grocery_list import _load_week_plan_names

    path = tmp_path / "week_plan.json"
    path.write_text("{not json", encoding="utf-8")
    assert _load_week_plan_names(path) == []
    assert "could not read week plan" in capsys.readouterr().err


def test_load_week_plan_names_oserror_returns_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Patch read_text to raise OSError and assert _load_week_plan_names returns [] gracefully."""
    from pathlib import Path as _Path

    from src.grocery_wizard.shopping.grocery_list import _load_week_plan_names

    path = tmp_path / "week_plan.json"
    path.write_text('{"recipes": ["Soup"]}', encoding="utf-8")

    with patch.object(_Path, "read_text", side_effect=OSError("permission denied")):
        result = _load_week_plan_names(path)

    assert result == []
    assert "could not read week plan" in capsys.readouterr().err


def test_build_grocery_list_never_scrapes_with_empty_ingredients(tmp_path: Path) -> None:
    """build_grocery_list must never call scrape_recipe, even when ingredients are empty."""
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    empty = _recipe("No Ingredients", "")
    empty.ingredients = None

    db = MagicMock()
    db.query_recipes.return_value = [empty]

    # Patch at the scraper module to catch any accidental scraping from any code path
    with patch("src.grocery_wizard.recipes.scraper.scrape_recipe") as mock_scrape:
        _items, _excluded, _sync_summary, missing = build_grocery_list(
            db,
            recipe_names=["No Ingredients"],
            pantry_path=pantry_path,
        )
        mock_scrape.assert_not_called()

    assert missing == ["No Ingredients"]


def test_build_grocery_list_returns_missing_ingredients_for_empty_recipes(tmp_path: Path) -> None:
    """Recipes with empty Notion Ingredients are reported in missing_ingredients, not silently skipped."""
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    populated = _recipe("Populated", "1 cup flour\n2 eggs")
    empty = _recipe("Empty", "")
    empty.ingredients = None

    db = MagicMock()
    db.query_recipes.return_value = [populated, empty]

    items, _excluded, _sync_summary, missing = build_grocery_list(
        db,
        recipe_names=["Populated", "Empty"],
        pantry_path=pantry_path,
    )

    assert any("flour" in item or "eggs" in item for item in items), "populated recipe items should appear"
    assert missing == ["Empty"]


def test_run_grocery_list_backfill_missing_only_syncs_empty_recipes(tmp_path: Path) -> None:
    """--backfill-missing on CLI only syncs recipes that actually lack ingredients."""
    from src.grocery_wizard.ingredients.sync import SyncSummary

    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    populated = _recipe("Populated", "1 cup flour\n2 eggs")
    empty = _recipe("Empty", "")
    empty.ingredients = None

    db = MagicMock()
    db.query_recipes.side_effect = [
        [populated, empty],
        [populated, empty],
    ]

    week_plan = pantry_path.parent / "week_plan.json"
    week_plan.write_text('{"recipes": ["Populated", "Empty"]}', encoding="utf-8")

    captured: list = []

    def fake_run_sync_recipes(db_arg, recipes, **kwargs):
        captured.extend(recipes)
        return SyncSummary()

    with (
        patch(
            "src.grocery_wizard.shopping.grocery_list.run_sync_recipes",
            side_effect=fake_run_sync_recipes,
        ),
        patch(
            "src.grocery_wizard.shopping.grocery_list.prompt_recurring_weekly_items",
            return_value=[],
        ),
    ):
        code = run_grocery_list(
            db,
            backfill_missing=True,
            quiet=True,
            week_plan_path=week_plan,
            pantry_path=pantry_path,
        )

    assert code == 0
    assert len(captured) == 1
    assert captured[0].name == "Empty"


def test_build_grocery_list_splits_title_bleed(tmp_path: Path) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Chimichurri Chicken", "chimichurri zucchini orzo"),
    ]

    items, _, _, _ = build_grocery_list(
        db,
        recipe_names=["Chimichurri Chicken"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert "chimichurri" in items
    assert "zucchini" in items
    assert "orzo" in items
    assert "chimichurri zucchini orzo" not in items


def test_build_grocery_list_splits_merged_chermoula_lines(tmp_path: Path) -> None:
    """Regression: merged Notion lines must not become one grocery item."""
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe(
            "One-Pot Chermoula Shrimp and Orzo",
            "2 lemons\n"
            "3 cilantro flat leaves parsley olive oil cloves garlic\n"
            "ground cumin\n"
            "1 teaspoon fine sea salt, plus more to taste granulated sugar",
        ),
    ]

    items, _, _, _ = build_grocery_list(
        db,
        recipe_names=["One-Pot Chermoula Shrimp and Orzo"],
        pantry_path=pantry_path,
        exclude_pantry=False,
    )

    joined = " ".join(items).lower()
    assert "cilantro flat leaves parsley olive oil cloves garlic" not in joined
    assert "cilantro" in joined
    assert "garlic" in joined
    assert "olive oil" in joined
    assert "ground cumin" in joined
    assert "granulated sugar" in joined
    assert "2 lemons" in items


def test_build_grocery_list_aggregates_fractional_limes(tmp_path: Path) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Recipe A", "1 lime, cut into wedges"),
        _recipe("Recipe B", "1/2 lime"),
    ]

    items, _, _, _ = build_grocery_list(
        db,
        recipe_names=["Recipe A", "Recipe B"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert "2 limes" in items
    assert len([item for item in items if "lime" in item.lower()]) == 1


def test_build_grocery_list_shows_amounts(tmp_path: Path) -> None:
    """Amounts parsed from ingredient lines appear in the grocery list."""
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Soup", "1 lb chicken breast\n2 cans white beans"),
    ]

    items, _, _, _ = build_grocery_list(
        db,
        recipe_names=["Soup"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert "1 lb chicken breast" in items
    assert "2 cans white beans" in items


def test_build_grocery_list_aggregates_amounts_across_recipes(tmp_path: Path) -> None:
    """Same ingredient from two recipes has its amounts summed."""
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Recipe A", "1 can white beans"),
        _recipe("Recipe B", "1 can white beans"),
    ]

    items, _, _, _ = build_grocery_list(
        db,
        recipe_names=["Recipe A", "Recipe B"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert "2 cans white beans" in items
    assert len([item for item in items if "white beans" in item]) == 1


def test_build_grocery_list_no_amount_fallback(tmp_path: Path) -> None:
    """Ingredients without a quantity are still shown, just without a prefix."""
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Salad", "chicken breast"),
    ]

    items, _, _, _ = build_grocery_list(
        db,
        recipe_names=["Salad"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    assert "chicken breast" in items


def test_build_grocery_list_includes_recurring_weekly_items(tmp_path: Path) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Soup", "1 lb chicken breast"),
    ]

    items, _, _, _ = build_grocery_list(
        db,
        recipe_names=["Soup"],
        pantry_path=pantry_path,
        recurring_weekly_items=["berries", "bananas", "milk"],
        include_recurring_weekly_items=True,
    )

    assert "berries" in items
    assert "bananas" in items
    assert "milk" in items


def test_build_grocery_list_skips_duplicate_recurring_weekly_items(tmp_path: Path) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Soup", "2 cups milk"),
    ]

    items, _, _, _ = build_grocery_list(
        db,
        recipe_names=["Soup"],
        pantry_path=pantry_path,
        recurring_weekly_items=["milk"],
        include_recurring_weekly_items=True,
    )

    assert len([item for item in items if "milk" in item.lower()]) == 1


def test_build_grocery_list_skips_duplicate_recurring_banana_plural(tmp_path: Path) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe("Smoothie", "2 bananas"),
    ]

    items, _, _, _ = build_grocery_list(
        db,
        recipe_names=["Smoothie"],
        pantry_path=pantry_path,
        recurring_weekly_items=["bananas"],
        include_recurring_weekly_items=True,
    )

    assert len([item for item in items if "banana" in item.lower()]) == 1


def test_print_grocery_list_has_no_aisle_headers(capsys: pytest.CaptureFixture[str]) -> None:
    from src.grocery_wizard.shopping.grocery_list import _print_grocery_list

    _print_grocery_list(["eggs", "onions", "bananas"], heading=None)

    output = capsys.readouterr().out
    assert "Fruit" not in output
    assert "Vegetables" not in output
    assert "====" not in output
    assert "----" not in output
    assert output.strip().splitlines() == ["bananas", "onions", "eggs"]


def test_build_grocery_list_consolidates_lemon_variants(tmp_path: Path) -> None:
    pantry_path = tmp_path / "pantry.txt"
    pantry_path.write_text("salt\n", encoding="utf-8")

    db = MagicMock()
    db.query_recipes.return_value = [
        _recipe(
            "Lemon Dish",
            "juice of half a lemon\n1 lemon\nzest of 1 lemon",
        )
    ]

    items, _, _, _ = build_grocery_list(
        db,
        recipe_names=["Lemon Dish"],
        pantry_path=pantry_path,
        exclude_pantry=True,
    )

    lemon_items = [item for item in items if "lemon" in item.lower()]
    assert len(lemon_items) == 1
    assert lemon_items[0] == "3 lemons"
