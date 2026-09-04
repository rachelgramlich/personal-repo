"""Flow 1: Interactive weekly meal planning from Notion recipes."""

from __future__ import annotations

import difflib
import json
import random
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.grocery_wizard.config import WEEK_PLAN_PATH
from src.grocery_wizard.integrations.notion import ColumnInfo, NotionRecipesDB, Recipe
from src.grocery_wizard.lib.prompts import confirm_yes_default, parse_yes_no

DIVERSITY_COLUMNS = ("Protein", "Dinner Category", "Cuisine")

DEFAULT_FILTER_MEAL = "Dinner"
DEFAULT_FILTER_WEEKNIGHT_COLUMN = "Dinner: Weeknight Friendly"


@dataclass
class MealPlanFilters:
    """Per-column filter values. Omitted columns are not filtered."""

    values: dict[str, Any] = field(default_factory=dict)


def filter_recipes(
    recipes: list[Recipe],
    filters: MealPlanFilters,
    schema_columns: dict[str, ColumnInfo],
) -> list[Recipe]:
    """Return recipes matching all active filters."""
    if not filters.values:
        return list(recipes)

    return [recipe for recipe in recipes if recipe_matches_filters(recipe, filters, schema_columns)]


def recipe_matches_filters(
    recipe: Recipe,
    filters: MealPlanFilters,
    schema_columns: dict[str, ColumnInfo],
) -> bool:
    for column_name, filter_value in filters.values.items():
        column = schema_columns.get(column_name)
        if column is None:
            continue
        if not recipe_matches_column_filter(
            recipe.properties.get(column_name),
            filter_value,
            column.type,
        ):
            return False
    return True


def recipe_matches_column_filter(
    prop_value: Any,
    filter_value: Any,
    column_type: str,
) -> bool:
    if filter_value is None:
        return True

    if column_type in ("select", "status"):
        return prop_value == filter_value

    if column_type == "multi_select":
        if not filter_value:
            return True
        if not isinstance(filter_value, list):
            filter_value = [filter_value]
        if not isinstance(prop_value, list):
            return False
        return any(option in prop_value for option in filter_value)

    if column_type == "checkbox":
        return prop_value is filter_value

    return True


def default_filters(schema_columns: dict[str, ColumnInfo]) -> MealPlanFilters:
    """Default meal-plan filters: Dinner + weeknight-friendly."""
    values: dict[str, Any] = {}

    meal_col = schema_columns.get("Meal")
    if meal_col is not None and (not meal_col.options or DEFAULT_FILTER_MEAL in meal_col.options):
        values["Meal"] = DEFAULT_FILTER_MEAL

    if DEFAULT_FILTER_WEEKNIGHT_COLUMN in schema_columns:
        values[DEFAULT_FILTER_WEEKNIGHT_COLUMN] = True

    return MealPlanFilters(values=values)


def _recipe_tags(recipe: Recipe, column: str) -> set[str]:
    value = recipe.properties.get(column)
    if isinstance(value, list):
        return {str(item) for item in value}
    if value is not None and value != "":
        return {str(value)}
    return set()


def _shares_tag(recipe_a: Recipe, recipe_b: Recipe, column: str) -> bool:
    tags_a = _recipe_tags(recipe_a, column)
    tags_b = _recipe_tags(recipe_b, column)
    if not tags_a or not tags_b:
        return False
    return bool(tags_a & tags_b)


TOP_K_DIVERSE = 3

CHOICE_PROMPT = "\n[a]ccept  [r]eject  [p]ick from list: "


def _diversity_score(recipe: Recipe, selected: list[Recipe]) -> tuple[int, int, int]:
    used: dict[str, set[str]] = {col: set() for col in DIVERSITY_COLUMNS}
    for prior in selected:
        for column in DIVERSITY_COLUMNS:
            used[column].update(_recipe_tags(prior, column))

    protein_new = len(_recipe_tags(recipe, "Protein") - used["Protein"])
    category_new = len(_recipe_tags(recipe, "Dinner Category") - used["Dinner Category"])
    cuisine_new = len(_recipe_tags(recipe, "Cuisine") - used["Cuisine"])
    return (protein_new, category_new, cuisine_new)


def eligible_suggestion_pool(
    pool: list[Recipe],
    accepted_names: set[str],
    rejected_names: set[str],
) -> list[Recipe]:
    """Recipes still available for suggestion (not accepted or rejected this session)."""
    return [
        recipe
        for recipe in pool
        if recipe.name not in accepted_names and recipe.name not in rejected_names
    ]


def pick_diverse_recipe(
    candidates: list[Recipe],
    selected: list[Recipe],
    *,
    top_k: int = TOP_K_DIVERSE,
) -> Recipe:
    """Pick a recipe favoring variety, sampling randomly among the top diverse options."""
    if not candidates:
        raise ValueError("candidates must not be empty")
    if len(candidates) == 1:
        return candidates[0]

    pool = list(candidates)
    if selected:
        last = selected[-1]
        without_repeat = [recipe for recipe in pool if not _shares_tag(recipe, last, "Protein")]
        if without_repeat:
            pool = without_repeat

    scored = sorted(
        ((recipe, _diversity_score(recipe, selected)) for recipe in pool),
        key=lambda item: item[1],
        reverse=True,
    )
    top = scored[: min(top_k, len(scored))]
    return random.choice([recipe for recipe, _ in top])


def select_diverse_meals(pool: list[Recipe], count: int) -> list[Recipe]:
    """Select up to count recipes with diversified protein, category, and cuisine."""
    remaining = list(pool)
    selected: list[Recipe] = []
    for _ in range(count):
        if not remaining:
            break
        pick = pick_diverse_recipe(remaining, selected)
        selected.append(pick)
        remaining = [recipe for recipe in remaining if recipe.page_id != pick.page_id]
    return selected


def fuzzy_match_recipes(query: str, recipes: list[Recipe]) -> list[Recipe]:
    """Match a user request to recipe names (case-insensitive, substring, or fuzzy)."""
    query = query.strip()
    if not query:
        return []

    query_lower = query.lower()
    exact = [recipe for recipe in recipes if recipe.name.lower() == query_lower]
    if exact:
        return exact

    substring = [recipe for recipe in recipes if query_lower in recipe.name.lower()]
    if substring:
        return substring

    names = [recipe.name for recipe in recipes]
    close_names = difflib.get_close_matches(query, names, n=5, cutoff=0.5)
    return [recipe for recipe in recipes if recipe.name in close_names]


def parse_meal_requests(raw: str) -> list[str]:
    """Parse comma-separated meal request strings."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def _resolve_locked_by_names(
    locked_names: list[str],
    all_recipes: list[Recipe],
) -> list[Recipe]:
    """Resolve locked recipe names to Recipe objects, preserving order and skipping duplicates."""
    recipe_by_name = {recipe.name: recipe for recipe in all_recipes}
    locked: list[Recipe] = []
    seen_ids: set[str] = set()
    for name in locked_names:
        recipe = recipe_by_name.get(name)
        if recipe is None or recipe.page_id in seen_ids:
            continue
        locked.append(recipe)
        seen_ids.add(recipe.page_id)
    return locked


def suggest_meals(
    all_recipes: list[Recipe],
    *,
    meals: int,
    locked_names: list[str] | None = None,
    filters: MealPlanFilters | None = None,
    schema_columns: dict[str, ColumnInfo],
) -> list[str]:
    """Suggest a meal plan: locked recipes first, then diverse auto-filled slots."""
    active_filters = filters if filters is not None else default_filters(schema_columns)
    locked_recipes = _resolve_locked_by_names(locked_names or [], all_recipes)[:meals]

    full_pool = filter_recipes(all_recipes, active_filters, schema_columns)
    locked_ids = {recipe.page_id for recipe in locked_recipes}
    pool = [recipe for recipe in full_pool if recipe.page_id not in locked_ids]

    remaining_slots = meals - len(locked_recipes)
    suggested: list[str] = []
    if remaining_slots > 0 and pool:
        picked = select_diverse_meals(pool, remaining_slots)
        suggested = [recipe.name for recipe in picked]

    return [recipe.name for recipe in locked_recipes] + suggested


def replace_meals_in_plan(
    plan_names: list[str],
    names_to_replace: list[str],
    *,
    all_recipes: list[Recipe],
    pool: list[Recipe],
    rejected_names: set[str] | None = None,
) -> tuple[list[str], set[str]]:
    """Swap named meals for diverse alternatives, tracking rejected names for the session."""
    if not names_to_replace:
        return list(plan_names), set(rejected_names or ())

    recipe_by_name = {recipe.name: recipe for recipe in all_recipes}
    updated = list(plan_names)
    session_rejected = set(rejected_names or ())
    replace_set = set(names_to_replace)

    for index, name in enumerate(updated):
        if name not in replace_set:
            continue

        session_rejected.add(name)
        accepted_names = {plan_name for slot, plan_name in enumerate(updated) if slot != index}
        plan_recipes = [
            recipe_by_name[plan_name] for plan_name in accepted_names if plan_name in recipe_by_name
        ]
        candidates = eligible_suggestion_pool(pool, accepted_names, session_rejected)
        old_recipe = recipe_by_name.get(name)
        if old_recipe is not None:
            without_old = [recipe for recipe in candidates if recipe.page_id != old_recipe.page_id]
            if without_old:
                candidates = without_old

        if not candidates:
            continue

        replacement = pick_diverse_recipe(candidates, plan_recipes)
        updated[index] = replacement.name

    return updated, session_rejected


def save_week_plan(recipe_names: list[str], path: Path = WEEK_PLAN_PATH) -> Path:
    """Persist finalized plan for grocery_list.py."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"recipes": [name.strip() for name in recipe_names if name.strip()]}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def run_meal_planner(
    db: NotionRecipesDB,
    *,
    meals: int,
    week_plan_path: Path = WEEK_PLAN_PATH,
    prompt: Callable[[str], str] | None = None,
    confirm: Callable[[str], bool] | None = None,
) -> list[str]:
    """Interactive CLI meal planning. Returns finalized recipe names."""
    prompt_fn = prompt or input
    confirm_fn = confirm or confirm_yes_default

    all_recipes = db.query_recipes()
    schema = db.schema
    filterable_columns = [*schema.filter_columns, *schema.checkbox_columns]

    print(f"\nLoaded {len(all_recipes)} recipe(s) from Notion.\n")

    meal_count = _prompt_meal_count(meals, prompt_fn)
    locked_recipes = _resolve_specific_meals(all_recipes, meal_count, prompt_fn)

    if locked_recipes:
        print("\nLocked-in meals:")
        for index, recipe in enumerate(locked_recipes, start=1):
            print(f"  {index}. {recipe.name}")

    filters = _resolve_filters(filterable_columns, schema.all_columns, prompt_fn)
    full_pool = filter_recipes(all_recipes, filters, schema.all_columns)
    locked_ids = {recipe.page_id for recipe in locked_recipes}
    pool = [recipe for recipe in full_pool if recipe.page_id not in locked_ids]
    print(f"\nFiltered: {len(pool)} recipe(s) match (excluding locked-in meals).\n")

    remaining_slots = meal_count - len(locked_recipes)
    suggested_names: list[str] = []
    rejected_names: set[str] = set()

    if remaining_slots > 0:
        if not pool:
            print(
                "No recipes match your filters for remaining slots.",
                file=sys.stderr,
            )
        elif remaining_slots > len(pool):
            print(
                f"Warning: only {len(pool)} recipe(s) available "
                f"but {remaining_slots} slot(s) remain.",
                file=sys.stderr,
            )
            suggested_names = _build_plan_interactive(
                pool,
                remaining_slots,
                schema,
                prompt_fn,
                start_slot=len(locked_recipes) + 1,
                total_slots=meal_count,
                prior_recipes=locked_recipes,
                rejected_names=rejected_names,
            )
        else:
            suggested_names = _build_plan_interactive(
                pool,
                remaining_slots,
                schema,
                prompt_fn,
                start_slot=len(locked_recipes) + 1,
                total_slots=meal_count,
                prior_recipes=locked_recipes,
                rejected_names=rejected_names,
            )

    plan = [recipe.name for recipe in locked_recipes] + suggested_names
    if not plan:
        print("\nNo meals selected — week plan not saved.")
        return []

    plan = _review_plan_interactive(
        plan,
        full_pool,
        all_recipes,
        rejected_names,
        schema,
        prompt_fn,
    )

    if not confirm_fn(f"\nSave {len(plan)} meal(s) to {week_plan_path}?"):
        print("Not saved.")
        return plan

    saved_path = save_week_plan(plan, week_plan_path)
    print(f"Saved week plan ({len(plan)} recipe(s)) to {saved_path}.")
    return plan


def _prompt_meal_count(default: int, prompt_fn: Callable[[str], str]) -> int:
    while True:
        answer = prompt_fn(f"How many meals this week? [{default}]: ").strip()
        if not answer:
            return default
        if answer.isdigit() and int(answer) > 0:
            return int(answer)
        print("Enter a positive number, or press Enter for the default.")


def _resolve_specific_meals(
    all_recipes: list[Recipe],
    meal_count: int,
    prompt_fn: Callable[[str], str],
) -> list[Recipe]:
    raw = prompt_fn(
        "\nAny specific meals you want this week? (comma-separated names, or Enter to skip): "
    ).strip()
    if not raw:
        return []

    requests = parse_meal_requests(raw)
    locked: list[Recipe] = []
    seen_ids: set[str] = set()

    for request in requests:
        if len(locked) >= meal_count:
            print(f"\nAlready have {meal_count} meal(s) — skipping remaining requests.")
            break

        matches = fuzzy_match_recipes(request, all_recipes)
        if not matches:
            print(f"\nNo match for '{request}' — skipping.")
            continue

        picked = _pick_fuzzy_match(request, matches, prompt_fn)
        if picked is None:
            print(f"\nNo match for '{request}' — skipping.")
            continue

        if picked.page_id in seen_ids:
            print(f"\n'{picked.name}' is already in the plan — skipping duplicate.")
            continue

        locked.append(picked)
        seen_ids.add(picked.page_id)

    return locked


def _pick_fuzzy_match(
    request: str,
    matches: list[Recipe],
    prompt_fn: Callable[[str], str],
) -> Recipe | None:
    if len(matches) == 1:
        return matches[0]

    print(f"\nMultiple matches for '{request}':")
    for index, recipe in enumerate(matches, start=1):
        print(f"  {index}. {recipe.name}")
    print("  0. Skip")

    while True:
        choice = prompt_fn("  Choice: ").strip()
        if choice in ("", "0"):
            return None
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(matches):
                return matches[index - 1]
        print("  Invalid choice, try again.")


def _print_final_plan(plan: list[str]) -> None:
    print("\nFinal plan:")
    for index, name in enumerate(plan, start=1):
        print(f"  {index}. {name}")


def _resolve_slot_interactive(
    pool: list[Recipe],
    plan_recipes: list[Recipe],
    accepted_names: set[str],
    rejected_names: set[str],
    schema,
    prompt_fn: Callable[[str], str],
    *,
    exclude_recipe: Recipe | None = None,
) -> Recipe | None:
    """Prompt until user accepts a recipe for one slot. Returns recipe or None."""
    candidates = eligible_suggestion_pool(pool, accepted_names, rejected_names)
    if not candidates:
        return None

    pick_pool = candidates
    if exclude_recipe is not None:
        without_excluded = [
            recipe for recipe in candidates if recipe.page_id != exclude_recipe.page_id
        ]
        if without_excluded:
            pick_pool = without_excluded

    current = pick_diverse_recipe(pick_pool, plan_recipes)

    while True:
        _print_recipe_summary(current, schema)
        choice = prompt_fn(CHOICE_PROMPT).strip().lower()

        if choice in ("a", "accept"):
            return current

        if choice in ("r", "reject", "skip"):
            rejected_names.add(current.name)
            candidates = eligible_suggestion_pool(pool, accepted_names, rejected_names)
            if not candidates:
                print("No more alternatives for this slot.")
                return None
            current = pick_diverse_recipe(candidates, plan_recipes)
            continue

        if choice in ("p", "pick"):
            picked = _pick_from_list(
                eligible_suggestion_pool(pool, accepted_names, rejected_names),
                current,
                accepted_names,
                rejected_names,
                prompt_fn,
            )
            if picked is not None:
                current = picked
            continue

        print("Enter a, r, or p.")


def _review_plan_interactive(
    plan: list[str],
    pool: list[Recipe],
    all_recipes: list[Recipe],
    rejected_names: set[str],
    schema,
    prompt_fn: Callable[[str], str],
) -> list[str]:
    """Let user regenerate individual slots before saving."""
    recipe_by_name = {recipe.name: recipe for recipe in all_recipes}
    updated = list(plan)

    while True:
        _print_final_plan(updated)
        answer = prompt_fn(
            f"\nRegenerate a slot? (enter number 1-{len(updated)}, or Enter to continue): "
        ).strip()
        if not answer:
            break
        if not answer.isdigit():
            print("Enter a slot number, or press Enter to continue.")
            continue

        slot_num = int(answer)
        if not 1 <= slot_num <= len(updated):
            print(f"Enter a number between 1 and {len(updated)}.")
            continue

        print(f"\n--- Regenerating meal {slot_num} ---")
        old_recipe = recipe_by_name.get(updated[slot_num - 1])
        accepted_names = {name for index, name in enumerate(updated, start=1) if index != slot_num}
        plan_recipes = [recipe_by_name[name] for name in accepted_names if name in recipe_by_name]

        replacement = _resolve_slot_interactive(
            pool,
            plan_recipes,
            accepted_names,
            rejected_names,
            schema,
            prompt_fn,
            exclude_recipe=old_recipe,
        )
        if replacement is not None:
            updated[slot_num - 1] = replacement.name

    return updated


def _build_plan_interactive(
    pool: list[Recipe],
    meals: int,
    schema,
    prompt_fn: Callable[[str], str],
    *,
    start_slot: int = 1,
    total_slots: int | None = None,
    prior_recipes: list[Recipe] | None = None,
    rejected_names: set[str] | None = None,
) -> list[str]:
    plan: list[str] = []
    plan_recipes: list[Recipe] = list(prior_recipes or [])
    accepted_names: set[str] = {recipe.name for recipe in plan_recipes}
    session_rejected = rejected_names if rejected_names is not None else set()
    display_total = total_slots if total_slots is not None else meals

    for offset in range(meals):
        slot = start_slot + offset
        print(f"\n--- Meal {slot} of {display_total} ---")

        accepted = _resolve_slot_interactive(
            pool,
            plan_recipes,
            accepted_names,
            session_rejected,
            schema,
            prompt_fn,
        )
        if accepted is None:
            print(f"\nNo more recipes available after {len(plan)} suggested meal(s).")
            break

        plan.append(accepted.name)
        plan_recipes.append(accepted)
        accepted_names.add(accepted.name)

    return plan


def _pick_from_list(
    candidates: list[Recipe],
    current: Recipe,
    accepted_names: set[str],
    rejected_names: set[str],
    prompt_fn: Callable[[str], str],
) -> Recipe | None:
    options = [
        recipe
        for recipe in [current, *candidates]
        if recipe.name not in accepted_names and recipe.name not in rejected_names
    ]
    options = list({recipe.page_id: recipe for recipe in options}.values())
    if not options:
        print("No recipes to pick from.")
        return None

    print("\nPick a recipe:")
    for index, recipe in enumerate(options, start=1):
        marker = " (current)" if recipe.page_id == current.page_id else ""
        print(f"  {index}. {recipe.name}{marker}")
    print("  0. Cancel")

    while True:
        choice = prompt_fn("  Choice: ").strip()
        if choice in ("", "0"):
            return None
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(options):
                picked = options[index - 1]
                if picked.name in accepted_names:
                    print("  That recipe is already in the plan.")
                    continue
                if picked.name in rejected_names:
                    print("  That recipe was rejected earlier.")
                    continue
                return picked
        print("  Invalid choice, try again.")


def _print_recipe_summary(recipe: Recipe, schema) -> None:
    del schema  # suggestions show recipe name only
    print(f"Suggested: {recipe.name}")


def _resolve_filters(
    columns: list[ColumnInfo],
    schema_columns: dict[str, ColumnInfo],
    prompt_fn: Callable[[str], str],
) -> MealPlanFilters:
    defaults = default_filters(schema_columns)
    if defaults.values:
        print(f"Using default filters: {_format_filters(defaults)}")
    else:
        print("No default filters apply to this database schema.")

    if parse_yes_no(prompt_fn("\nChange filters? [y/N]: "), default_yes=False):
        return _prompt_filters(columns, prompt_fn)
    return defaults


def _format_filters(filters: MealPlanFilters) -> str:
    return ", ".join(f"{name}={_format_value(value)}" for name, value in filters.values.items())


def _prompt_filters(
    columns: list[ColumnInfo],
    prompt_fn: Callable[[str], str],
) -> MealPlanFilters:
    if not parse_yes_no(prompt_fn("Set filters? [Y/n]: "), default_yes=True):
        return MealPlanFilters()

    values: dict[str, Any] = {}
    print()

    for column in columns:
        if column.type in ("select", "status"):
            picked = _prompt_select_filter(column, prompt_fn)
            if picked is not None:
                values[column.name] = picked
        elif column.type == "multi_select":
            picked = _prompt_multi_select_filter(column, prompt_fn)
            if picked:
                values[column.name] = picked
        elif column.type == "checkbox":
            picked = _prompt_checkbox_filter(column, prompt_fn)
            if picked is not None:
                values[column.name] = picked

    return MealPlanFilters(values=values)


def _prompt_select_filter(
    column: ColumnInfo,
    prompt_fn: Callable[[str], str],
) -> str | None:
    print(f"{column.name} ({column.type}) — 0 to skip")
    for index, option in enumerate(column.options, start=1):
        print(f"  {index}. {option}")
    choice = prompt_fn("  Choice: ").strip()
    if not choice or choice == "0":
        return None
    if choice.isdigit():
        index = int(choice)
        if 1 <= index <= len(column.options):
            return column.options[index - 1]
    if choice in column.options:
        return choice
    print("  Invalid choice, skipping column.")
    return None


def _prompt_multi_select_filter(
    column: ColumnInfo,
    prompt_fn: Callable[[str], str],
) -> list[str] | None:
    print(f"{column.name} ({column.type}) — include any of (Enter to skip)")
    for index, option in enumerate(column.options, start=1):
        print(f"  {index}. {option}")
    choice = prompt_fn("  Choice (comma-separated numbers or names): ").strip()
    if not choice:
        return None

    picked: list[str] = []
    for part in choice.split(","):
        part = part.strip()
        if not part:
            continue
        if part.isdigit():
            index = int(part)
            if 1 <= index <= len(column.options):
                picked.append(column.options[index - 1])
                continue
        if part in column.options:
            picked.append(part)
            continue
        print("  Invalid choice, skipping column.")
        return None

    return list(dict.fromkeys(picked)) if picked else None


def _prompt_checkbox_filter(
    column: ColumnInfo,
    prompt_fn: Callable[[str], str],
) -> bool | None:
    print(f"{column.name} (checkbox) — y=yes, n=no, Enter to skip")
    while True:
        choice = prompt_fn("  Choice: ").strip().lower()
        if not choice:
            return None
        if choice in ("y", "yes"):
            return True
        if choice in ("n", "no"):
            return False
        print("  Enter y, n, or Enter to skip.")


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)
