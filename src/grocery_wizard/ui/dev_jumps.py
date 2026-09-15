"""Dev-mode jump-to-step helpers for faster manual UI UAT."""

from __future__ import annotations

import random
from enum import StrEnum
from typing import Any

from src.grocery_wizard.integrations.notion import NotionRecipesDB, Recipe
from src.grocery_wizard.ui.grocery_flow import (
    clear_grocery_session_overrides,
    default_pre_build_grocery_options,
    stash_grocery_result,
    stash_recipe_review,
)

DEFAULT_DEV_MEAL_COUNT = 1
_DEV_MEAL_PICK_SEED = 142


class DevJumpTarget(StrEnum):
    MEALS_FILLED = "meals_filled"
    PRE_BUILD_GROCERY = "pre_build_grocery"
    PER_RECIPE_REVIEW = "per_recipe_review"
    GROCERY_RESULT = "grocery_result"


DEV_JUMP_FLOW_ORDER: tuple[DevJumpTarget, ...] = (
    DevJumpTarget.MEALS_FILLED,
    DevJumpTarget.PRE_BUILD_GROCERY,
    DevJumpTarget.PER_RECIPE_REVIEW,
    DevJumpTarget.GROCERY_RESULT,
)


def dev_jump_display_title(target: DevJumpTarget) -> str:
    return {
        DevJumpTarget.MEALS_FILLED: "Meals filled",
        DevJumpTarget.PRE_BUILD_GROCERY: "Pre-build grocery",
        DevJumpTarget.PER_RECIPE_REVIEW: "Per-recipe review",
        DevJumpTarget.GROCERY_RESULT: "Final list",
    }[target]


DEV_JUMP_CAPTIONS: dict[DevJumpTarget, str] = {
    DevJumpTarget.MEALS_FILLED: (
        "Meal plan list (section **1. Meals**) — use **auto** for a default sample or "
        "**manual** to pick specific Notion recipes."
    ),
    DevJumpTarget.PRE_BUILD_GROCERY: (
        "Grocery setup (section **2. Grocery list**) — options expander and "
        "**Create grocery list**."
    ),
    DevJumpTarget.PER_RECIPE_REVIEW: (
        "Per-recipe ingredient review — edit lines in expanders before the list is built."
    ),
    DevJumpTarget.GROCERY_RESULT: (
        "Final list — built grocery list with re-add/remove, copy, and meals."
    ),
}


def pick_default_recipe_names(
    all_recipes: list[Recipe],
    *,
    meal_count: int = DEFAULT_DEV_MEAL_COUNT,
) -> list[str]:
    """Pick a small set of Notion recipes with ingredients for dev jumps."""
    with_ingredients = [recipe for recipe in all_recipes if (recipe.ingredients or "").strip()]
    pool = with_ingredients or list(all_recipes)
    if not pool:
        return []
    rng = random.Random(_DEV_MEAL_PICK_SEED)
    shuffled = sorted(pool, key=lambda recipe: recipe.name.lower())
    rng.shuffle(shuffled)
    return [recipe.name for recipe in shuffled[:meal_count]]


def clear_grocery_flow_state(session_state: Any) -> None:
    """Drop grocery result, review UI, and run-scoped pantry/recurring overrides."""
    for key in (
        "grocery_result",
        "grocery_readd",
        "grocery_remove_once",
        "grocery_final_list",
        "grocery_final_list_fingerprint",
        "meals_final_list",
        "meals_final_list_fingerprint",
        "grocery_per_recipe_review",
        "grocery_review_options",
        "grocery_review_recipes",
    ):
        session_state.pop(key, None)
    for key in list(session_state.keys()):
        if key.startswith("review_ing_"):
            session_state.pop(key, None)
    clear_grocery_session_overrides(session_state)


def commit_dev_jump(
    session_state: Any,
    db: NotionRecipesDB,
    target: DevJumpTarget,
    names: list[str],
) -> list[str]:
    """Apply a dev jump after recipe names are chosen; returns ``names`` used."""
    cleaned = [name for name in names if name.strip()]
    if not cleaned:
        return []

    clear_grocery_flow_state(session_state)
    session_state["plan_meals_text"] = "\n".join(cleaned)
    session_state.pop("plan_rejected_names", None)
    session_state.pop("weekly_plan_last_saved_name", None)
    session_state.pop("weekly_plan_saved_fingerprint", None)

    if target in (DevJumpTarget.MEALS_FILLED, DevJumpTarget.PRE_BUILD_GROCERY):
        return cleaned

    grocery_options = default_pre_build_grocery_options(session_state)
    recipes = db.query_recipes()

    if target == DevJumpTarget.PER_RECIPE_REVIEW:
        stash_recipe_review(session_state, cleaned, recipes, grocery_options)
        return cleaned

    if target == DevJumpTarget.GROCERY_RESULT:
        stash_grocery_result(session_state, db, cleaned, grocery_options, recipes=recipes)
        return cleaned

    return cleaned


def apply_dev_jump(
    session_state: Any,
    db: NotionRecipesDB,
    target: DevJumpTarget,
    *,
    meal_count: int = DEFAULT_DEV_MEAL_COUNT,
    recipe_names: list[str] | None = None,
) -> list[str]:
    """Resolve recipe names then commit the jump (CLI/tests helper)."""
    if recipe_names is not None:
        names = list(recipe_names)
    else:
        names = pick_default_recipe_names(db.query_recipes(), meal_count=meal_count)
    return commit_dev_jump(session_state, db, target, names)
