"""Shared grocery-list wizard state and build logic (Streamlit UI + dev jumps)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.grocery_wizard.ingredients.sync import format_ingredients_for_review
from src.grocery_wizard.integrations.notion import NotionRecipesDB
from src.grocery_wizard.shopping.grocery_list import build_grocery_list
from src.grocery_wizard.shopping.line_items import parse_line_items
from src.grocery_wizard.shopping.recurring_weekly_items import (
    apply_recurring_session_overrides,
    load_recurring_weekly_items,
)


@dataclass(frozen=True)
class GroceryPreBuildOptions:
    exclude_pantry: bool
    recurring_text: str
    default_recurring: list[str]
    extra_items_text: str


def grocery_pre_extra_items_widget_key(session_state: Any) -> str:
    epoch = int(session_state.get("grocery_pre_extra_items_epoch", 0))
    return f"grocery_pre_extra_items_{epoch}"


def bump_grocery_pre_extra_items_widget(session_state: Any) -> None:
    session_state["grocery_pre_extra_items_epoch"] = (
        int(session_state.get("grocery_pre_extra_items_epoch", 0)) + 1
    )


def session_pantry_extra(session_state: Any) -> set[str]:
    if "grocery_session_pantry" not in session_state:
        session_state["grocery_session_pantry"] = set()
    return session_state["grocery_session_pantry"]


def session_recurring_removals(session_state: Any) -> set[str]:
    if "grocery_session_recurring_removals" not in session_state:
        session_state["grocery_session_recurring_removals"] = set()
    return session_state["grocery_session_recurring_removals"]


def session_recurring_additions(session_state: Any) -> list[str]:
    if "grocery_session_recurring_additions" not in session_state:
        session_state["grocery_session_recurring_additions"] = []
    return session_state["grocery_session_recurring_additions"]


def clear_grocery_session_overrides(session_state: Any) -> None:
    session_state.pop("grocery_session_pantry", None)
    session_state.pop("grocery_session_recurring_removals", None)
    session_state.pop("grocery_session_recurring_additions", None)
    bump_grocery_pre_extra_items_widget(session_state)


def effective_recurring_items(session_state: Any, template: list[str]) -> list[str]:
    return apply_recurring_session_overrides(
        template,
        additions=session_recurring_additions(session_state),
        removals=session_recurring_removals(session_state),
    )


def default_pre_build_grocery_options(session_state: Any) -> GroceryPreBuildOptions:
    """Defaults matching section **2. Grocery list** before the user edits widgets."""
    template_recurring = load_recurring_weekly_items()
    default_recurring = effective_recurring_items(session_state, template_recurring)
    extra_key = grocery_pre_extra_items_widget_key(session_state)
    extra_items_text = str(session_state.get(extra_key, "") or "")
    return GroceryPreBuildOptions(
        exclude_pantry=True,
        recurring_text="\n".join(default_recurring),
        default_recurring=list(default_recurring),
        extra_items_text=extra_items_text,
    )


def fetch_recipe_review_text(db: NotionRecipesDB, selected: list[str]) -> dict[str, str]:
    recipes_by_name = {recipe.name.lower(): recipe for recipe in db.query_recipes()}
    review: dict[str, str] = {}
    for name in selected:
        recipe = recipes_by_name.get(name.lower())
        raw = recipe.ingredients or "" if recipe else ""
        review[name] = format_ingredients_for_review(raw)
    return review


def stash_recipe_review(
    session_state: Any,
    db: NotionRecipesDB,
    selected: list[str],
    options: GroceryPreBuildOptions,
) -> None:
    session_state["grocery_per_recipe_review"] = fetch_recipe_review_text(db, selected)
    session_state["grocery_review_options"] = {
        "exclude_pantry": options.exclude_pantry,
        "recurring_text": options.recurring_text,
        "default_recurring": options.default_recurring,
        "extra_items_text": options.extra_items_text,
    }


def ingredient_overrides_from_review(review: dict[str, str]) -> dict[str, str]:
    return {name.lower(): text for name, text in review.items()}


def build_grocery_result_payload(
    db: NotionRecipesDB,
    selected: list[str],
    *,
    exclude_pantry: bool,
    recurring_text: str,
    extra_items_text: str,
    pantry_extra: set[str],
    ingredient_overrides: dict[str, str] | None,
    edit_count: int = 0,
) -> dict[str, Any]:
    recurring_weekly_items = parse_line_items(recurring_text)
    items, excluded, _sync_summary, missing_ingredients, item_provenance, mismatches = (
        build_grocery_list(
            db,
            recipe_names=selected,
            exclude_pantry=exclude_pantry,
            pantry_extra=pantry_extra,
            recurring_weekly_items=recurring_weekly_items,
            include_recurring_weekly_items=True,
            ingredient_overrides=ingredient_overrides,
        )
    )
    return {
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
        "edit_count": edit_count,
    }


def stash_grocery_result(
    session_state: Any,
    db: NotionRecipesDB,
    selected: list[str],
    options: GroceryPreBuildOptions,
    *,
    review: dict[str, str] | None = None,
    edit_count: int = 0,
) -> None:
    """Build final list as if the user confirmed review (defaults: formatted Notion lines)."""
    review_text = review if review is not None else fetch_recipe_review_text(db, selected)
    session_state["grocery_result"] = build_grocery_result_payload(
        db,
        selected,
        exclude_pantry=options.exclude_pantry,
        recurring_text=options.recurring_text,
        extra_items_text=options.extra_items_text,
        pantry_extra=session_pantry_extra(session_state),
        ingredient_overrides=ingredient_overrides_from_review(review_text),
        edit_count=edit_count,
    )
