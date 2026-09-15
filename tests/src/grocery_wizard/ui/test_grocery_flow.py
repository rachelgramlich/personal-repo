"""Tests for shared grocery wizard flow helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.grocery_wizard.integrations.notion import Recipe
from src.grocery_wizard.ui.grocery_flow import (
    GroceryPreBuildOptions,
    default_pre_build_grocery_options,
    fetch_recipe_review_text,
    stash_grocery_result,
    stash_recipe_review,
)


def _recipe(name: str, *, ingredients: str = "1 cup flour") -> Recipe:
    return Recipe(
        page_id=name,
        name=name,
        link=None,
        ingredients=ingredients,
        properties={},
    )


def test_fetch_recipe_review_text_formats_notion_storage() -> None:
    db = MagicMock()
    stored = "clove:5 garlic"
    db.query_recipes.return_value = [_recipe("Soup", ingredients=stored)]
    review = fetch_recipe_review_text(db, ["Soup"])
    assert "5 cloves garlic" in review["Soup"]
    assert "clove:5" not in review["Soup"]


def test_stash_recipe_review_uses_formatted_text(monkeypatch: pytest.MonkeyPatch) -> None:
    session: dict = {}
    db = MagicMock()
    db.query_recipes.return_value = [_recipe("Soup", ingredients="raw")]
    monkeypatch.setattr(
        "src.grocery_wizard.ui.grocery_flow.format_ingredients_for_review",
        lambda raw: f"formatted:{raw}",
    )
    opts = GroceryPreBuildOptions(
        exclude_pantry=True,
        recurring_text="banana",
        default_recurring=["banana"],
        extra_items_text="",
    )
    stash_recipe_review(session, db, ["Soup"], opts)
    assert session["grocery_per_recipe_review"]["Soup"] == "formatted:raw"


def test_stash_grocery_result_passes_review_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    session: dict = {}
    db = MagicMock()
    db.query_recipes.return_value = [_recipe("Soup")]
    build_mock = MagicMock(return_value=(["flour"], [], None, [], {}, []))
    monkeypatch.setattr(
        "src.grocery_wizard.ui.grocery_flow.build_grocery_list",
        build_mock,
    )
    opts = GroceryPreBuildOptions(
        exclude_pantry=True,
        recurring_text="",
        default_recurring=[],
        extra_items_text="flowers",
    )
    review = {"Soup": "1 cup flour\n"}
    stash_grocery_result(session, db, ["Soup"], opts, review=review)
    build_mock.assert_called_once()
    _args, kwargs = build_mock.call_args
    assert kwargs["ingredient_overrides"] == {"soup": "1 cup flour\n"}
    assert session["grocery_result"]["additional_text"] == "flowers"


def test_default_pre_build_respects_session_recurring() -> None:
    session = {
        "grocery_session_recurring_additions": ["flowers"],
        "grocery_pre_extra_items_epoch": 0,
        "grocery_pre_extra_items_0": "extra line",
    }
    opts = default_pre_build_grocery_options(session)
    assert "flowers" in opts.default_recurring
    assert opts.extra_items_text == "extra line"
