"""Flow 2: Build a merged grocery list from planned recipes."""

from __future__ import annotations

__all__ = [
    "build_grocery_list",
    "format_grocery_item",
    "format_meals_and_grocery_list",
    "format_sync_message",
    "run_grocery_list",
]

import difflib
import json
import sys
from pathlib import Path

from src.grocery_wizard.config import LEGACY_WEEK_PLAN_PATH, WEEK_PLAN_PATH
from src.grocery_wizard.ingredients.normalize import (
    aggregate_amounts,
    expand_ingredient_line,
    normalize_ingredient,
    parse_amount,
    should_show_amount,
)
from src.grocery_wizard.ingredients.sync import (
    SyncSummary,
    format_sync_summary,
    parse_ingredients_text,
    recipe_needs_empty_sync,
    run_sync_recipes,
)
from src.grocery_wizard.integrations.notion import NotionRecipesDB, Recipe
from src.grocery_wizard.shopping.pantry import is_pantry_item, load_pantry
from src.grocery_wizard.shopping.recurring_weekly_items import prompt_recurring_weekly_items
from src.grocery_wizard.shopping.store_aisles import (
    ingredient_name,
    sort_grocery_items,
)


def run_grocery_list(
    db: NotionRecipesDB,
    *,
    recipe_names: list[str] | None = None,
    quiet: bool = False,
    backfill_missing: bool = False,
    staples: list[str] | None = None,
    week_plan_path: Path = WEEK_PLAN_PATH,
    pantry_path: Path | None = None,
    recurring_weekly_items_path: Path | None = None,
    recurring_weekly_items: list[str] | None = None,
    include_recurring_weekly_items: bool = True,
    exclude_pantry: bool = True,
) -> int:
    """Generate a merged grocery list from week plan or explicit recipe names."""
    names = recipe_names or _load_week_plan_names(week_plan_path)
    if not names:
        print(
            "No recipes to build a list from.\n"
            'Run `plan-recipes` first, or pass --recipes "Name1,Name2".',
            file=sys.stderr,
        )
        return 1

    recipes_by_name = {recipe.name.lower(): recipe for recipe in db.query_recipes()}
    if backfill_missing:
        needs_backfill = _recipes_needing_backfill(names, recipes_by_name)
        if needs_backfill:
            summary = run_sync_recipes(db, needs_backfill)
            print(format_sync_message(summary))
            recipes_by_name = {recipe.name.lower(): recipe for recipe in db.query_recipes()}

    pantry = load_pantry(pantry_path)

    # collected maps normalized_name_lower → (display_name, [amounts])
    collected: dict[str, tuple[str, list[str | None]]] = {}
    excluded_pantry: list[str] = []

    for name in names:
        recipe = recipes_by_name.get(name.lower())
        if recipe is None:
            print(f"Warning: recipe not found in Notion: {name}", file=sys.stderr)
            continue

        ingredient_lines = _get_ingredient_lines(recipe)
        if not ingredient_lines:
            print(
                f"Warning: skipping '{recipe.name}' — no ingredients in Notion. "
                "Run `dev backfill-ingredients` to populate from the link.",
                file=sys.stderr,
            )
            continue

        for line in ingredient_lines:
            _collect_ingredient_line(
                line,
                pantry=pantry,
                exclude_pantry=exclude_pantry,
                collected=collected,
                excluded_pantry=excluded_pantry,
            )

    seen: set[str] = set(collected.keys())
    grocery_items: list[str] = [
        format_grocery_item(display_name, aggregate_amounts(amounts, name=display_name))
        for display_name, amounts in collected.values()
    ]

    excluded_sorted = sorted(excluded_pantry, key=str.lower)

    if not quiet:
        _print_excluded_summary(excluded_sorted)
        readded = _prompt_readd_excluded(excluded_sorted)
        if readded:
            existing = {item.lower() for item in grocery_items}
            for item in readded:
                if item.lower() not in existing:
                    grocery_items.append(item)
                    existing.add(item.lower())

        recurring = _resolve_recurring_weekly_items(
            recurring_weekly_items=recurring_weekly_items,
            recurring_weekly_items_path=recurring_weekly_items_path,
            include=include_recurring_weekly_items,
            interactive=True,
        )
        _append_unique_items(grocery_items, seen, recurring)

        grocery_items = sort_grocery_items(grocery_items)
        _print_grocery_list(grocery_items, heading="Draft grocery list")

        extra_staples = staples if staples is not None else _prompt_staples()
        for staple in extra_staples:
            key = staple.lower()
            if key not in seen:
                seen.add(key)
                grocery_items.append(staple)

        grocery_items = sort_grocery_items(grocery_items)
        _print_grocery_list(grocery_items, heading="Grocery list")
        grocery_items = _prompt_accept_or_edit(grocery_items)
        _print_grocery_list(grocery_items, heading="Final grocery list")
    else:
        recurring = _resolve_recurring_weekly_items(
            recurring_weekly_items=recurring_weekly_items,
            recurring_weekly_items_path=recurring_weekly_items_path,
            include=include_recurring_weekly_items,
            interactive=False,
        )
        _append_unique_items(grocery_items, seen, recurring)
        for staple in staples or []:
            key = staple.lower()
            if key not in seen:
                seen.add(key)
                grocery_items.append(staple)
        grocery_items = sort_grocery_items(grocery_items)
        _print_grocery_list(grocery_items)

    return 0


def build_grocery_list(
    db: NotionRecipesDB,
    *,
    recipe_names: list[str],
    staples: list[str] | None = None,
    week_plan_path: Path = WEEK_PLAN_PATH,
    pantry_path: Path | None = None,
    recurring_weekly_items_path: Path | None = None,
    recurring_weekly_items: list[str] | None = None,
    include_recurring_weekly_items: bool = False,
    exclude_pantry: bool = True,
) -> tuple[list[str], list[str], list[str]]:
    """Build grocery list items, excluded pantry items, and skipped recipe names (for UI use).

    Reads ingredients exclusively from Notion — never scrapes. Recipes whose
    Notion Ingredients field is empty are collected in the returned
    ``missing_ingredients`` list so callers can surface a backfill hint.
    """
    recipes_by_name = {recipe.name.lower(): recipe for recipe in db.query_recipes()}
    pantry = load_pantry(pantry_path)

    # collected maps normalized_name_lower → (display_name, [amounts])
    collected: dict[str, tuple[str, list[str | None]]] = {}
    excluded_pantry: list[str] = []
    missing_ingredients: list[str] = []

    for name in recipe_names:
        recipe = recipes_by_name.get(name.lower())
        if recipe is None:
            continue

        ingredient_lines = _get_ingredient_lines(recipe)
        if not ingredient_lines:
            missing_ingredients.append(recipe.name)
            continue

        for line in ingredient_lines:
            _collect_ingredient_line(
                line,
                pantry=pantry,
                exclude_pantry=exclude_pantry,
                collected=collected,
                excluded_pantry=excluded_pantry,
            )

    seen: set[str] = set(collected.keys())
    grocery_items: list[str] = [
        format_grocery_item(display_name, aggregate_amounts(amounts, name=display_name))
        for display_name, amounts in collected.values()
    ]

    for staple in staples or []:
        key = staple.lower()
        if key not in seen:
            seen.add(key)
            grocery_items.append(staple)

    if include_recurring_weekly_items:
        recurring = (
            recurring_weekly_items
            if recurring_weekly_items is not None
            else prompt_recurring_weekly_items(
                path=recurring_weekly_items_path,
                interactive=False,
            )
        )
        _append_unique_items(grocery_items, seen, recurring)

    grocery_items = sort_grocery_items(grocery_items)
    excluded_pantry.sort(key=str.lower)
    return grocery_items, excluded_pantry, missing_ingredients


def format_sync_message(summary: SyncSummary) -> str:
    return format_sync_summary(summary)


def _load_week_plan_names(path: Path) -> list[str]:
    resolved = path
    if not resolved.exists():
        if path == WEEK_PLAN_PATH and LEGACY_WEEK_PLAN_PATH.exists():
            resolved = LEGACY_WEEK_PLAN_PATH
        else:
            return []

    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: could not read week plan ({resolved}): {exc}", file=sys.stderr)
        return []
    if isinstance(data, dict):
        recipes = data.get("recipes", [])
        if isinstance(recipes, list):
            return [str(name).strip() for name in recipes if str(name).strip()]
    if isinstance(data, list):
        return [str(name).strip() for name in data if str(name).strip()]
    return []


def _get_ingredient_lines(recipe: Recipe) -> list[str]:
    if recipe.ingredients and recipe.ingredients.strip():
        return parse_ingredients_text(recipe.ingredients)[0]
    return []


def format_grocery_item(name: str, amount: str | None) -> str:
    """Format a grocery item for display: ``"amount name"`` or just ``name``."""
    if amount is None:
        return name
    return f"{amount} {name}"


def format_meals_and_grocery_list(
    meals: list[tuple[str, str | None]],
    grocery_items: list[str],
) -> str:
    """Format meals and grocery items as a single copy/pasteable block."""
    lines = ["Meals"]
    for name, link in meals:
        if link:
            lines.append(f"- {name} ({link})")
        else:
            lines.append(f"- {name}")

    lines.append("")
    lines.append("Grocery List")
    lines.extend(f"- {item}" for item in sort_grocery_items(grocery_items))

    return "\n".join(lines)


def _resolve_recurring_weekly_items(
    *,
    recurring_weekly_items: list[str] | None,
    recurring_weekly_items_path: Path | None,
    include: bool,
    interactive: bool,
) -> list[str]:
    if not include:
        return []
    if recurring_weekly_items is not None:
        return recurring_weekly_items
    return prompt_recurring_weekly_items(
        path=recurring_weekly_items_path,
        interactive=interactive,
    )


def _normalized_item_key(name: str) -> str:
    return (normalize_ingredient(name) or name.strip()).lower()


def _append_unique_items(
    grocery_items: list[str],
    seen: set[str],
    new_items: list[str],
) -> None:
    """Add items that are not already present on the list or in *seen*."""
    for item in new_items:
        cleaned = item.strip()
        if not cleaned:
            continue
        key = _normalized_item_key(cleaned)
        if _item_already_present(cleaned, seen, grocery_items):
            continue
        seen.add(key)
        grocery_items.append(cleaned)


def _item_already_present(name: str, seen: set[str], grocery_items: list[str]) -> bool:
    key = _normalized_item_key(name)
    if key in seen:
        return True
    return any(_normalized_item_key(ingredient_name(item)) == key for item in grocery_items)


def _collect_ingredient_line(
    line: str,
    *,
    pantry: set[str],
    exclude_pantry: bool,
    collected: dict[str, tuple[str, list[str | None]]],
    excluded_pantry: list[str],
) -> None:
    """Parse *line*, deduplicate by normalised name, and accumulate amounts.

    Pantry items are routed to *excluded_pantry* instead of *collected*.
    Ingredient lines are expected to be pre-cleaned at Notion ingest time.
    """
    for part in expand_ingredient_line(line):
        normalized, amount = parse_amount(part)
        if not normalized:
            continue
        keeps_amount = amount and not amount.startswith(("head:", "clove:", "zest:"))
        if keeps_amount and not should_show_amount(amount, part):
            amount = None
        if exclude_pantry and is_pantry_item(normalized, pantry):
            if normalized not in excluded_pantry:
                excluded_pantry.append(normalized)
            continue
        key = normalized.lower()
        if key in collected:
            collected[key][1].append(amount)
        else:
            collected[key] = (normalized, [amount])


def _split_ingredient_text(text: str) -> list[str]:
    """Deprecated: use parse_ingredients_text from sync instead."""
    return parse_ingredients_text(text)[0]


def match_excluded_items(query: str, excluded: list[str]) -> list[str]:
    """Match user input to excluded pantry items (exact, substring, or fuzzy)."""
    query = query.strip()
    if not query or not excluded:
        return []

    query_lower = query.lower()
    exact = [item for item in excluded if item.lower() == query_lower]
    if exact:
        return exact

    substring = [item for item in excluded if query_lower in item.lower()]
    if substring:
        return substring

    return difflib.get_close_matches(query, excluded, n=5, cutoff=0.5)


def parse_readd_excluded(raw: str, excluded: list[str]) -> list[str]:
    """Parse comma-separated names or numbers referencing the excluded list."""
    selected: list[str] = []
    seen: set[str] = set()

    for part in (piece.strip() for piece in raw.split(",") if piece.strip()):
        if part.isdigit():
            index = int(part) - 1
            if 0 <= index < len(excluded):
                item = excluded[index]
                key = item.lower()
                if key not in seen:
                    seen.add(key)
                    selected.append(item)
            continue

        for item in match_excluded_items(part, excluded):
            key = item.lower()
            if key not in seen:
                seen.add(key)
                selected.append(item)

    return selected


def _print_grocery_list(items: list[str], *, heading: str | None = "Grocery list") -> None:
    if heading is not None:
        print()
        print(heading)
        print("=" * 40)

    sorted_items = sort_grocery_items(items)
    for item in sorted_items:
        print(item)


def _recipes_needing_backfill(
    names: list[str],
    recipes_by_name: dict[str, Recipe],
) -> list[Recipe]:
    needs: list[Recipe] = []
    for name in names:
        recipe = recipes_by_name.get(name.lower())
        if recipe and recipe_needs_empty_sync(recipe):
            needs.append(recipe)
    return needs


def _print_excluded_summary(excluded: list[str]) -> None:
    if not excluded:
        return
    print()
    print("Excluded staples (already in your pantry)")
    print("-" * 40)
    for index, item in enumerate(excluded, start=1):
        print(f"  {index}. {item}")


def _prompt_readd_excluded(excluded: list[str]) -> list[str]:
    if not excluded:
        return []

    print()
    try:
        raw = input(
            "Add excluded staples back? (numbers or names, comma-separated — Enter to skip): "
        )
    except EOFError:
        return []

    if not raw.strip():
        return []
    return parse_readd_excluded(raw, excluded)


def _prompt_staples() -> list[str]:
    print()
    print("Paste any additional items (one per line, empty line when done):")
    staples: list[str] = []
    while True:
        try:
            line = input().strip()
        except EOFError:
            break
        if not line:
            break
        if line.startswith(("- ", "* ", "• ")):
            line = line[2:].strip()
        if line:
            staples.append(line)
    return staples


def _prompt_accept_or_edit(items: list[str]) -> list[str]:
    print()
    while True:
        try:
            raw = input("Accept list? [Enter] accept, [e] edit: ").strip().lower()
        except EOFError:
            return items

        if raw in ("", "y", "yes"):
            return items
        if raw in ("e", "edit"):
            print("Paste your edited list (one per line, empty line when done):")
            edited = _prompt_staples()
            if edited:
                return sort_grocery_items(edited)
            return items

        print("Press Enter to accept or type 'e' to edit.")
