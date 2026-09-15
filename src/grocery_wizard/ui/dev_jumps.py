"""Dev-mode jump-to-step helpers for faster manual UI UAT."""

from __future__ import annotations

import random
from enum import StrEnum
from typing import Any

from src.grocery_wizard.integrations.notion import NotionRecipesDB, Recipe
from src.grocery_wizard.shopping.grocery_list import build_grocery_list
from src.grocery_wizard.shopping.recurring_weekly_items import load_recurring_weekly_items

DEFAULT_DEV_MEAL_COUNT = 1
_DEV_MEAL_PICK_SEED = 142


class DevJumpTarget(StrEnum):
    MEALS_FILLED = "meals_filled"
    PRE_BUILD_GROCERY = "pre_build_grocery"
    PER_RECIPE_REVIEW = "per_recipe_review"
    GROCERY_RESULT = "grocery_result"


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
        "Per-recipe ingredient review — expanders and **Build final list**."
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


def _recipes_by_name(db: NotionRecipesDB) -> dict[str, Recipe]:
    return {recipe.name.lower(): recipe for recipe in db.query_recipes()}


def _default_grocery_options() -> tuple[bool, str, list[str], str]:
    exclude_pantry = True
    template_recurring = load_recurring_weekly_items()
    default_recurring = list(template_recurring)
    recurring_text = "\n".join(default_recurring)
    extra_items_text = ""
    return exclude_pantry, recurring_text, default_recurring, extra_items_text


def _stash_recipe_review(
    session_state: Any,
    db: NotionRecipesDB,
    selected: list[str],
    *,
    exclude_pantry: bool,
    recurring_text: str,
    default_recurring: list[str],
    extra_items_text: str,
) -> None:
    recipes_by_name = _recipes_by_name(db)
    review: dict[str, str] = {}
    for name in selected:
        recipe = recipes_by_name.get(name.lower())
        review[name] = recipe.ingredients or "" if recipe else ""
    session_state["grocery_per_recipe_review"] = review
    session_state["grocery_review_options"] = {
        "exclude_pantry": exclude_pantry,
        "recurring_text": recurring_text,
        "default_recurring": default_recurring,
        "extra_items_text": extra_items_text,
    }


def _stash_grocery_result(
    session_state: Any,
    db: NotionRecipesDB,
    selected: list[str],
    *,
    exclude_pantry: bool,
    recurring_text: str,
    extra_items_text: str,
) -> None:
    from src.grocery_wizard.shopping.line_items import parse_line_items

    recurring_weekly_items = parse_line_items(recurring_text)
    items, excluded, _sync_summary, missing_ingredients, item_provenance, mismatches = (
        build_grocery_list(
            db,
            recipe_names=selected,
            exclude_pantry=exclude_pantry,
            pantry_extra=set(),
            recurring_weekly_items=recurring_weekly_items,
            include_recurring_weekly_items=True,
            ingredient_overrides=None,
        )
    )
    session_state["grocery_result"] = {
        "items": items,
        "excluded": excluded,
        "missing_ingredients": missing_ingredients,
        "item_provenance": item_provenance,
        "name_link_mismatches": mismatches,
        "readd": [],
        "additional_text": extra_items_text,
        "recurring_items": list(recurring_weekly_items),
        "run_removals": [],
        "source_recipes": tuple(selected),
        "week_plan": tuple(selected),
        "edit_count": 0,
    }


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
        "grocery_session_pantry",
        "grocery_session_recurring_removals",
        "grocery_session_recurring_additions",
    ):
        session_state.pop(key, None)
    for key in list(session_state.keys()):
        if key.startswith("review_ing_"):
            session_state.pop(key, None)


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

    exclude_pantry, recurring_text, default_recurring, extra_items_text = _default_grocery_options()

    if target == DevJumpTarget.PER_RECIPE_REVIEW:
        _stash_recipe_review(
            session_state,
            db,
            cleaned,
            exclude_pantry=exclude_pantry,
            recurring_text=recurring_text,
            default_recurring=default_recurring,
            extra_items_text=extra_items_text,
        )
        return cleaned

    if target == DevJumpTarget.GROCERY_RESULT:
        _stash_grocery_result(
            session_state,
            db,
            cleaned,
            exclude_pantry=exclude_pantry,
            recurring_text=recurring_text,
            extra_items_text=extra_items_text,
        )
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
