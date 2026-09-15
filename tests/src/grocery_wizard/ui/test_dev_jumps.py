"""Tests for dev-mode jump-to-step helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.grocery_wizard.integrations.notion import Recipe
from src.grocery_wizard.ui.dev_jumps import (
    DEFAULT_DEV_MEAL_COUNT,
    DevJumpTarget,
    apply_dev_jump,
    clear_grocery_flow_state,
    commit_dev_jump,
    pick_default_recipe_names,
)


def test_default_dev_meal_count_is_one() -> None:
    assert DEFAULT_DEV_MEAL_COUNT == 1


def _recipe(name: str, *, ingredients: str = "1 cup flour") -> Recipe:
    return Recipe(
        page_id=name,
        name=name,
        link=None,
        ingredients=ingredients,
        properties={},
    )


def test_pick_default_recipe_names_prefers_recipes_with_ingredients() -> None:
    recipes = [
        _recipe("Empty", ingredients=""),
        _recipe("Alpha"),
        _recipe("Beta"),
        _recipe("Gamma"),
    ]
    names = pick_default_recipe_names(recipes, meal_count=2)
    assert len(names) == 2
    assert "Empty" not in names
    assert set(names) <= {"Alpha", "Beta", "Gamma"}


def test_pick_default_recipe_names_is_deterministic() -> None:
    recipes = [_recipe(f"Recipe {i}") for i in range(10)]
    first = pick_default_recipe_names(recipes, meal_count=3)
    second = pick_default_recipe_names(recipes, meal_count=3)
    assert first == second
    assert len(first) == 3


def test_apply_dev_jump_meals_filled_sets_plan_text_only() -> None:
    session = {}
    db = MagicMock()
    db.query_recipes.return_value = [_recipe("Soup"), _recipe("Salad")]
    db.schema.all_columns = {}

    used = apply_dev_jump(session, db, DevJumpTarget.MEALS_FILLED, meal_count=2)

    assert set(used) == {"Soup", "Salad"}
    assert set(session["plan_meals_text"].splitlines()) == {"Soup", "Salad"}
    assert "grocery_per_recipe_review" not in session
    assert "grocery_result" not in session


def test_apply_dev_jump_grocery_result_builds_result(monkeypatch: pytest.MonkeyPatch) -> None:
    session = {}
    db = MagicMock()
    db.query_recipes.return_value = [_recipe("Soup")]
    db.schema.all_columns = {}

    build_mock = MagicMock(return_value=(["flour"], [], None, [], {}, []))
    monkeypatch.setattr(
        "src.grocery_wizard.ui.grocery_flow.build_grocery_list",
        build_mock,
    )

    used = apply_dev_jump(session, db, DevJumpTarget.GROCERY_RESULT, meal_count=1)

    assert used == ["Soup"]
    assert session["grocery_result"]["items"] == ["flour"]
    assert session["grocery_result"]["week_plan"] == ("Soup",)


def test_commit_dev_jump_accepts_explicit_recipe_names() -> None:
    session = {}
    db = MagicMock()

    used = commit_dev_jump(
        session,
        db,
        DevJumpTarget.MEALS_FILLED,
        ["Custom A", "Custom B"],
    )

    assert used == ["Custom A", "Custom B"]
    assert session["plan_meals_text"] == "Custom A\nCustom B"


def test_apply_dev_jump_accepts_explicit_recipe_names() -> None:
    session = {}
    db = MagicMock()
    db.query_recipes.return_value = []

    used = apply_dev_jump(
        session,
        db,
        DevJumpTarget.MEALS_FILLED,
        recipe_names=["Custom A", "Custom B"],
    )

    assert used == ["Custom A", "Custom B"]
    assert session["plan_meals_text"] == "Custom A\nCustom B"


def test_clear_grocery_flow_state_removes_review_widgets() -> None:
    session = {
        "grocery_result": {},
        "review_ing_0": "x",
        "plan_meals_text": "keep",
    }
    clear_grocery_flow_state(session)
    assert "grocery_result" not in session
    assert "review_ing_0" not in session
    assert session["plan_meals_text"] == "keep"
