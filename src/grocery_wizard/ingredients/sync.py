"""Scrape recipe links and persist or merge raw ingredients in Notion."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

import requests

from src.grocery_wizard.ingredients.normalize import (
    expand_ingredient_line,
    is_instruction_line,
    is_junk_ingredient,
    is_metadata_line,
    is_recipe_step_line,
    normalize_ingredient,
    split_merged_ingredient_line,
)
from src.grocery_wizard.integrations.notion import NotionRecipesDB, Recipe
from src.grocery_wizard.recipes.scraper import (
    ScrapeError,
    ingredients_to_text,
    scrape_recipe,
)

_REMOVAL_PREFIX_RE = re.compile(r"^remove\s*:?\s*(.+)$", re.IGNORECASE)
_REMOVAL_DASH_RE = re.compile(r"^-\s+(.+)$")
_BR_SPLIT = re.compile(r"<br\s*/?>", re.IGNORECASE)


@dataclass
class SyncResult:
    recipe_name: str
    status: str  # synced, skipped, failed, dry_run, merged, kept, replaced, edited
    message: str = ""
    ingredient_count: int | None = None
    ingredient_lines: list[str] | None = None


@dataclass
class RecipeCategories:
    empty: list[Recipe] = field(default_factory=list)
    populated: list[Recipe] = field(default_factory=list)
    no_link: list[Recipe] = field(default_factory=list)


@dataclass
class RefreshResult:
    recipe_name: str
    status: str  # updated, skipped, failed, dry_run, unchanged
    message: str = ""
    ingredient_count: int | None = None
    ingredient_lines: list[str] | None = None


@dataclass
class RefreshSummary:
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    updated_names: list[str] = field(default_factory=list)
    dry_run: list[str] = field(default_factory=list)
    results: list[RefreshResult] = field(default_factory=list)


@dataclass
class SyncSummary:
    synced: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    synced_names: list[str] = field(default_factory=list)
    dry_run: list[str] = field(default_factory=list)
    merge_accepted: int = 0
    merge_kept: int = 0
    merge_replaced: int = 0
    merge_skipped: int = 0
    merge_edited: int = 0
    categories: RecipeCategories | None = None
    results: list[SyncResult] = field(default_factory=list)


def split_ingredients_text(text: str) -> str:
    """Re-split stored ingredients, preserving directives and comments."""
    if not text or not text.strip():
        return ""

    output_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if is_directive(line):
            output_lines.append(line)
            continue
        output_lines.extend(expand_ingredient_line(line))
    return ingredients_to_text(output_lines)


def _normalize_stored_lines(text: str) -> list[str]:
    """Normalize bullets, HTML breaks, and unicode from stored ingredient text."""
    if not text or not text.strip():
        return []

    normalized = _BR_SPLIT.sub("\n", text)
    lines: list[str] = []
    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        line = re.sub(r"^[▢•*]\s*", "", line)
        line = re.sub(r"^\\[ \\]\s*▢?", "", line).strip()
        line = re.sub(r"^\d+\.\s*(?:\[\s*\]\s*)", "", line).strip()
        if line.startswith(("- ", "* ")):
            line = line[2:].strip()
        elif len(line) > 1 and line[0] == "-" and line[1].isdigit():
            line = line[1:].strip()
        if line:
            lines.append(line)
    return lines


def _repair_mangled_lines(lines: list[str]) -> list[str]:
    """Split merged scrape artifacts into one ingredient per line."""
    repaired: list[str] = []
    for line in lines:
        if is_directive(line):
            repaired.append(line)
            continue
        repaired.extend(split_merged_ingredient_line(line))
    return repaired


def _merge_continuation_lines(lines: list[str]) -> list[str]:
    """Join ingredient lines broken across rows (e.g. unclosed parentheses)."""
    merged: list[str] = []
    for line in lines:
        if is_directive(line):
            merged.append(line)
            continue
        stripped = line.strip()
        if (
            is_junk_ingredient(stripped)
            or is_instruction_line(stripped)
            or is_metadata_line(stripped)
        ):
            merged.append(stripped)
            continue
        if (
            merged
            and not is_directive(merged[-1])
            and _is_ingredient_continuation(merged[-1], stripped)
        ):
            merged[-1] = f"{merged[-1]} {stripped}"
        else:
            merged.append(stripped)
    return merged


def _is_ingredient_continuation(previous: str, current: str) -> bool:
    if previous.count("(") > previous.count(")"):
        return True
    stripped = current.strip()
    if not stripped:
        return False
    prev_words = previous.split()
    if len(prev_words) == 1 and prev_words[0][0].isupper():
        return False
    if stripped[0].islower() and not re.match(r"^\d", stripped):
        return True
    return False


def _truncate_at_instructions(lines: list[str]) -> list[str]:
    """Drop recipe steps and everything after the first numbered instruction."""
    kept: list[str] = []
    for line in lines:
        if is_directive(line):
            kept.append(line)
            continue
        if is_recipe_step_line(line):
            break
        if is_metadata_line(line) or is_instruction_line(line):
            continue
        kept.append(line)
    return kept


def prepare_ingredients_for_notion(text: str) -> str:
    """Clean, split, and normalize ingredient text before storing in Notion."""
    lines = _normalize_stored_lines(text)
    if not lines:
        return ""

    lines = _repair_mangled_lines(lines)
    lines = _merge_continuation_lines(lines)
    lines = _truncate_at_instructions(lines)

    split = split_ingredients_text(ingredients_to_text(lines))
    if not split.strip():
        return ""

    kept: list[str] = []
    for line in split.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if is_directive(stripped):
            kept.append(stripped)
            continue
        if (
            is_metadata_line(stripped)
            or is_instruction_line(stripped)
            or is_junk_ingredient(stripped)
        ):
            continue
        if stripped.lower() == "recipe":
            continue
        kept.append(stripped)
    return ingredients_to_text(kept)


def refresh_ingredients_for_recipe(
    db: NotionRecipesDB,
    recipe: Recipe,
    *,
    dry_run: bool = False,
    split_only: bool = False,
) -> RefreshResult:
    """Scrape (or reuse) ingredients, split compounds, and write to Notion."""
    if not db.schema.ingredients_column:
        return RefreshResult(recipe.name, "failed", "no Ingredients column detected")

    source_text: str | None = None

    if split_only:
        if not recipe.ingredients or not recipe.ingredients.strip():
            return RefreshResult(recipe.name, "skipped", "no ingredients")
        source_text = recipe.ingredients
    else:
        if not recipe.link:
            return RefreshResult(recipe.name, "skipped", "no link")
        try:
            source_text = scrape_ingredients_text(recipe.link)
        except (ScrapeError, requests.RequestException) as exc:
            return RefreshResult(recipe.name, "failed", str(exc))
        except Exception as exc:
            return RefreshResult(recipe.name, "failed", str(exc))

    refreshed_text = prepare_ingredients_for_notion(source_text)
    ingredient_lines = [
        line for line in refreshed_text.splitlines() if line.strip() and not is_directive(line)
    ]
    if not ingredient_lines:
        return RefreshResult(recipe.name, "failed", "no ingredients found")

    if refreshed_text == (recipe.ingredients or "").strip():
        return RefreshResult(
            recipe.name,
            "unchanged",
            ingredient_count=len(ingredient_lines),
            ingredient_lines=ingredient_lines,
        )

    if dry_run:
        return RefreshResult(
            recipe.name,
            "dry_run",
            ingredient_count=len(ingredient_lines),
            ingredient_lines=ingredient_lines,
        )

    db.update_recipe(
        recipe.page_id,
        {db.schema.ingredients_column: refreshed_text},
    )
    return RefreshResult(
        recipe.name,
        "updated",
        ingredient_count=len(ingredient_lines),
        ingredient_lines=ingredient_lines,
    )


def run_refresh_ingredients(
    db: NotionRecipesDB,
    *,
    dry_run: bool = False,
    split_only: bool = False,
    on_recipe_done: Callable[[int, int, RefreshResult], None] | None = None,
) -> RefreshSummary:
    """Refresh all recipes: scrape ingredients, split compounds, write to Notion."""
    recipes = db.query_recipes()
    summary = RefreshSummary()
    total = len(recipes)

    for index, recipe in enumerate(recipes, start=1):
        try:
            result = refresh_ingredients_for_recipe(
                db,
                recipe,
                dry_run=dry_run,
                split_only=split_only,
            )
        except Exception as exc:
            result = RefreshResult(recipe.name, "failed", str(exc))

        summary.results.append(result)
        if result.status in ("updated", "dry_run"):
            summary.updated += 1
            summary.updated_names.append(recipe.name)
            if dry_run:
                summary.dry_run.append(recipe.name)
        elif result.status == "unchanged":
            summary.unchanged += 1
        elif result.status == "skipped":
            summary.skipped += 1
        elif result.status == "failed":
            summary.failed.append(f"{recipe.name}: {result.message}")

        if on_recipe_done is not None:
            on_recipe_done(index, total, result)

    return summary


def format_refresh_progress(index: int, total: int, result: RefreshResult) -> str:
    prefix = f"[{index}/{total}] {result.recipe_name} ... "
    if result.status in ("updated", "dry_run"):
        count = result.ingredient_count or 0
        return f"{prefix}OK ({count} lines)"
    if result.status == "unchanged":
        count = result.ingredient_count or 0
        return f"{prefix}UNCHANGED ({count} lines)"
    if result.status == "failed":
        return f"{prefix}FAILED: {result.message}"
    if result.status == "skipped":
        return f"{prefix}SKIPPED ({result.message})"
    return f"{prefix}{result.status}"


def format_refresh_summary(
    summary: RefreshSummary,
    *,
    dry_run: bool = False,
    split_only: bool = False,
) -> str:
    parts: list[str] = ["Summary"]
    if dry_run:
        parts.append(f"  Would update: {summary.updated}")
    else:
        parts.append(f"  Updated:    {summary.updated}")
        if summary.updated_names:
            parts.extend(f"    - {name}" for name in summary.updated_names)
    parts.append(f"  Unchanged:  {summary.unchanged}")
    parts.append(f"  Skipped:    {summary.skipped}")
    if summary.failed:
        parts.append(f"  Failed:     {len(summary.failed)}")
        for failure in summary.failed:
            name, _, reason = failure.partition(": ")
            parts.append(f"    - {name}: {reason or failure}")
    mode = "split-only" if split_only else "scrape + split"
    parts.append(f"  Mode:       {mode}")
    return "\n".join(parts)


def scrape_ingredients_text(url: str) -> str:
    """Scrape a recipe URL and return newline-separated ingredient lines."""
    scraped = scrape_recipe(url)
    return ingredients_to_text(scraped.ingredients)


def is_removal_directive(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _REMOVAL_PREFIX_RE.match(stripped):
        return True
    match = _REMOVAL_DASH_RE.match(stripped)
    if not match:
        return False
    target = match.group(1).strip()
    if re.match(r"^\d", target):
        return False
    return True


def is_directive(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("#"):
        return True
    return is_removal_directive(stripped)


def parse_removal_target(line: str) -> str:
    stripped = line.strip()
    match = _REMOVAL_PREFIX_RE.match(stripped)
    if match:
        return match.group(1).strip()
    match = _REMOVAL_DASH_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def parse_ingredients_text(text: str) -> tuple[list[str], list[str]]:
    """Split stored ingredients into ingredient lines and removal targets."""
    ingredients: list[str] = []
    removals: list[str] = []
    if not text or not text.strip():
        return ingredients, removals

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if is_directive(line):
            if is_removal_directive(line):
                target = parse_removal_target(line)
                if target:
                    removals.append(target)
            continue
        ingredients.append(line)

    return ingredients, removals


def _normalized_set(lines: list[str]) -> set[str]:
    return {norm for line in lines if (norm := normalize_ingredient(line))}


def _line_represented(line: str, normalized_names: set[str]) -> bool:
    norm = normalize_ingredient(line)
    if not norm:
        return False
    return norm in normalized_names


def _matches_removal(line: str, removal_target: str) -> bool:
    normalized = normalize_ingredient(line)
    target_norm = normalize_ingredient(removal_target)
    if not normalized or not target_norm:
        return False
    if target_norm in normalized or normalized in target_norm:
        return True
    return False


def apply_removals(lines: list[str], removal_targets: list[str]) -> list[str]:
    if not removal_targets:
        return list(lines)
    return [
        line
        for line in lines
        if not any(_matches_removal(line, target) for target in removal_targets)
    ]


def merge_ingredients(existing: str, scraped: str) -> str:
    """Merge Notion ingredients with a freshly scraped list."""
    existing_lines, removals = parse_ingredients_text(existing)
    scraped_lines, _ = parse_ingredients_text(scraped)

    merged = list(scraped_lines)
    merged_norms = _normalized_set(scraped_lines)

    for line in existing_lines:
        if _line_represented(line, merged_norms):
            continue
        norm = normalize_ingredient(line)
        if not norm:
            continue
        merged.append(line)
        merged_norms.add(norm)

    merged = apply_removals(merged, removals)
    return ingredients_to_text(merged)


def categorize_recipes(recipes: list[Recipe]) -> RecipeCategories:
    categories = RecipeCategories()
    for recipe in recipes:
        if not recipe.link:
            categories.no_link.append(recipe)
            continue
        if recipe.ingredients and recipe.ingredients.strip():
            categories.populated.append(recipe)
        else:
            categories.empty.append(recipe)
    return categories


def recipe_needs_empty_sync(recipe: Recipe) -> bool:
    return bool(recipe.link) and not (recipe.ingredients and recipe.ingredients.strip())


def recipe_needs_merge(recipe: Recipe) -> bool:
    return bool(recipe.link) and bool(recipe.ingredients and recipe.ingredients.strip())


def recipe_needs_sync(recipe: Recipe, *, force: bool = False) -> bool:
    """Return True when a recipe should be batch-synced (empty Ingredients only)."""
    if not recipe.link:
        return False
    if recipe.ingredients and recipe.ingredients.strip():
        return False
    return True


def find_recipes_needing_sync(db: NotionRecipesDB, *, force: bool = False) -> list[Recipe]:
    return [recipe for recipe in db.query_recipes() if recipe_needs_sync(recipe, force=force)]


def find_recipes_needing_merge(db: NotionRecipesDB) -> list[Recipe]:
    return [recipe for recipe in db.query_recipes() if recipe_needs_merge(recipe)]


def sync_ingredients_for_recipe(
    db: NotionRecipesDB,
    recipe: Recipe,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> SyncResult:
    """Scrape recipe link and write raw ingredients to Notion (empty rows only)."""
    if not recipe.link:
        return SyncResult(recipe.name, "failed", "no link")

    if recipe.ingredients and recipe.ingredients.strip():
        return SyncResult(
            recipe.name,
            "skipped",
            "already has ingredients (use sync --merge)",
        )

    if not db.schema.ingredients_column:
        return SyncResult(recipe.name, "failed", "no Ingredients column detected")

    try:
        ingredients_text = scrape_ingredients_text(recipe.link)
    except ScrapeError as exc:
        return SyncResult(recipe.name, "failed", str(exc))
    except requests.RequestException as exc:
        return SyncResult(recipe.name, "failed", str(exc))
    except Exception as exc:
        return SyncResult(recipe.name, "failed", str(exc))

    prepared_text = prepare_ingredients_for_notion(ingredients_text)
    ingredient_lines = [
        line for line in prepared_text.splitlines() if line.strip() and not is_directive(line)
    ]
    if not ingredient_lines:
        return SyncResult(recipe.name, "failed", "no ingredients found on page")

    if dry_run:
        return SyncResult(
            recipe.name,
            "dry_run",
            ingredient_count=len(ingredient_lines),
            ingredient_lines=ingredient_lines,
        )

    db.update_recipe(
        recipe.page_id,
        {db.schema.ingredients_column: prepared_text},
    )
    return SyncResult(
        recipe.name,
        "synced",
        ingredient_count=len(ingredient_lines),
        ingredient_lines=ingredient_lines,
    )


def run_sync(
    db: NotionRecipesDB,
    *,
    dry_run: bool = False,
    force: bool = False,
    on_recipe_done: Callable[[int, int, SyncResult], None] | None = None,
) -> SyncSummary:
    """Phase A: batch sync recipes with Link filled and empty Ingredients."""
    recipes = db.query_recipes()
    categories = categorize_recipes(recipes)
    summary = SyncSummary(categories=categories)
    targets = list(categories.empty)
    total = len(targets)

    if dry_run:
        summary.dry_run = [recipe.name for recipe in targets]
        return summary

    for index, recipe in enumerate(targets, start=1):
        try:
            result = sync_ingredients_for_recipe(db, recipe, dry_run=False, force=force)
        except Exception as exc:
            result = SyncResult(recipe.name, "failed", str(exc))

        summary.results.append(result)
        if result.status == "synced":
            summary.synced += 1
            summary.synced_names.append(recipe.name)
        elif result.status == "failed":
            summary.failed.append(f"{recipe.name}: {result.message}")

        if on_recipe_done is not None:
            on_recipe_done(index, total, result)

    summary.skipped = len(categories.populated)
    return summary


def run_sync_recipes(
    db: NotionRecipesDB,
    recipes: list[Recipe],
    *,
    dry_run: bool = False,
    force: bool = False,
) -> SyncSummary:
    """Sync ingredients for a specific list of recipes (e.g. week-plan backfill)."""
    categories = categorize_recipes(db.query_recipes())
    summary = SyncSummary(categories=categories)

    if dry_run:
        summary.dry_run = [recipe.name for recipe in recipes]
        return summary

    for recipe in recipes:
        try:
            result = sync_ingredients_for_recipe(db, recipe, dry_run=False, force=force)
        except Exception as exc:
            result = SyncResult(recipe.name, "failed", str(exc))

        summary.results.append(result)
        if result.status == "synced":
            summary.synced += 1
            summary.synced_names.append(recipe.name)
        elif result.status == "failed":
            summary.failed.append(f"{recipe.name}: {result.message}")
        elif result.status == "skipped":
            summary.skipped += 1

    return summary


def run_merge_sync(
    db: NotionRecipesDB,
    *,
    dry_run: bool = False,
    prompt: Callable[[str], str] | None = None,
) -> SyncSummary:
    """Phase B: interactively merge populated recipes one at a time."""
    recipes = db.query_recipes()
    categories = categorize_recipes(recipes)
    summary = SyncSummary(categories=categories)
    prompt_fn = prompt or _default_prompt

    if not db.schema.ingredients_column:
        summary.failed.append("no Ingredients column detected")
        return summary

    populated = categories.populated
    if dry_run:
        summary.dry_run = [recipe.name for recipe in populated]
        return summary

    for recipe in populated:
        result = _interactive_merge_recipe(db, recipe, prompt_fn)
        if result.status == "merged":
            summary.merge_accepted += 1
        elif result.status == "kept":
            summary.merge_kept += 1
        elif result.status == "replaced":
            summary.merge_replaced += 1
        elif result.status == "skipped":
            summary.merge_skipped += 1
        elif result.status == "edited":
            summary.merge_edited += 1
        elif result.status == "failed":
            summary.failed.append(f"{recipe.name}: {result.message}")

    return summary


def _interactive_merge_recipe(
    db: NotionRecipesDB,
    recipe: Recipe,
    prompt_fn: Callable[[str], str],
) -> SyncResult:
    existing_text = recipe.ingredients or ""
    try:
        scraped_text = scrape_ingredients_text(recipe.link)
    except ScrapeError as exc:
        return SyncResult(recipe.name, "failed", str(exc))
    except requests.RequestException as exc:
        return SyncResult(recipe.name, "failed", str(exc))
    except Exception as exc:
        return SyncResult(recipe.name, "failed", str(exc))

    if not scraped_text.strip():
        return SyncResult(recipe.name, "failed", "no ingredients found on page")

    merged_text = merge_ingredients(existing_text, scraped_text)
    existing_lines = parse_ingredients_text(existing_text)[0]
    scraped_lines = parse_ingredients_text(scraped_text)[0]
    merged_lines = parse_ingredients_text(merged_text)[0]

    print(f"\nRecipe: {recipe.name}")
    print(f"Existing ({len(existing_lines)} lines):")
    _print_lines(existing_lines)
    print(f"Scraped ({len(scraped_lines)} lines):")
    _print_lines(scraped_lines)
    print(f"Merged preview ({len(merged_lines)} lines):")
    _print_lines(merged_lines)
    print("[a]ccept merged [k]eep existing only [r]eplace with scrape [s]kip [e]dit manually")

    while True:
        choice = prompt_fn("Choice: ").strip().lower()
        if choice in ("a", "accept"):
            db.update_recipe(
                recipe.page_id,
                {db.schema.ingredients_column: merged_text},
            )
            return SyncResult(recipe.name, "merged")
        if choice in ("k", "keep"):
            return SyncResult(recipe.name, "kept")
        if choice in ("r", "replace"):
            db.update_recipe(
                recipe.page_id,
                {db.schema.ingredients_column: scraped_text},
            )
            return SyncResult(recipe.name, "replaced")
        if choice in ("s", "skip"):
            return SyncResult(recipe.name, "skipped")
        if choice in ("e", "edit"):
            edited = _read_multiline_ingredients(prompt_fn)
            if not edited.strip():
                print("No lines entered, keeping existing.")
                return SyncResult(recipe.name, "kept")
            db.update_recipe(
                recipe.page_id,
                {db.schema.ingredients_column: edited},
            )
            return SyncResult(recipe.name, "edited")
        print("Invalid choice. Enter a, k, r, s, or e.")


def _print_lines(lines: list[str]) -> None:
    if not lines:
        print("  (empty)")
        return
    for line in lines:
        print(f"  {line}")


def _read_multiline_ingredients(prompt_fn: Callable[[str], str]) -> str:
    print("Paste ingredients (one per line, empty line to finish):")
    lines: list[str] = []
    while True:
        line = prompt_fn("")
        if not line.strip():
            break
        lines.append(line.strip())
    return ingredients_to_text(lines)


def _default_prompt(message: str) -> str:
    return input(message)


def format_recipe_progress(index: int, total: int, result: SyncResult) -> str:
    prefix = f"[{index}/{total}] {result.recipe_name} ... "
    if result.status == "synced":
        count = result.ingredient_count or 0
        return f"{prefix}OK ({count} ingredients)"
    if result.status == "failed":
        return f"{prefix}FAILED: {result.message}"
    return f"{prefix}{result.status}"


def format_sync_summary(
    summary: SyncSummary,
    *,
    dry_run: bool = False,
    merge: bool = False,
    verbose: bool = False,
) -> str:
    parts: list[str] = []

    if verbose and summary.categories:
        parts.append(_format_categories(summary.categories, dry_run=dry_run, merge=merge))

    if dry_run:
        if merge:
            count = len(summary.dry_run)
            parts.append(f"Would merge {count} populated recipe(s)")
            if count:
                parts.extend(f"  - {name}" for name in summary.dry_run)
        else:
            count = len(summary.dry_run)
            parts.append(f"Would sync {count} empty recipe(s)")
            if count:
                parts.extend(f"  - {name}" for name in summary.dry_run)
        return "\n".join(parts)

    if merge:
        parts.append("Summary")
        parts.append(f"  Accepted:  {summary.merge_accepted}")
        parts.append(f"  Kept:      {summary.merge_kept}")
        parts.append(f"  Replaced:  {summary.merge_replaced}")
        parts.append(f"  Edited:    {summary.merge_edited}")
        parts.append(f"  Skipped:   {summary.merge_skipped}")
    else:
        parts.append("Summary")
        parts.append(f"  Synced:    {summary.synced}")
        if summary.synced_names:
            parts.extend(f"    - {name}" for name in summary.synced_names)
        parts.append(f"  Skipped:   {summary.skipped} populated (use sync --merge)")

    if summary.failed:
        parts.append(f"  Failed:    {len(summary.failed)}")
        for failure in summary.failed:
            name, _, reason = failure.partition(": ")
            parts.append(f"    - {name}: {reason or failure}")

    return "\n".join(parts)


def _format_categories(
    categories: RecipeCategories,
    *,
    dry_run: bool = False,
    merge: bool = False,
) -> str:
    lines = ["Recipe categories:"]
    empty_names = ", ".join(recipe.name for recipe in categories.empty) or "(none)"
    populated_names = ", ".join(recipe.name for recipe in categories.populated) or "(none)"
    no_link_names = ", ".join(recipe.name for recipe in categories.no_link) or "(none)"

    if dry_run and not merge:
        lines.append(f"  Empty (would sync): {empty_names}")
        lines.append(f"  Populated (use --merge): {populated_names}")
    elif dry_run and merge:
        lines.append(f"  Empty (use default sync): {empty_names}")
        lines.append(f"  Populated (would merge): {populated_names}")
    else:
        lines.append(f"  Empty: {empty_names}")
        lines.append(f"  Populated: {populated_names}")

    lines.append(f"  No link: {no_link_names}")
    return "\n".join(lines)
