"""End-to-end validation: Notion recipes → meal plan → grocery list."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.grocery_wizard.config import WEEK_PLAN_PATH, load_config
from src.grocery_wizard.dev.audit import looks_suspicious_ingredients
from src.grocery_wizard.ingredients.normalize import (
    is_junk_ingredient,
    looks_like_merged_ingredient_line,
    normalize_ingredient,
)
from src.grocery_wizard.ingredients.sync import parse_ingredients_text
from src.grocery_wizard.integrations.notion import NotionRecipesDB, Recipe
from src.grocery_wizard.planning.meal_planner import default_filters, suggest_meals
from src.grocery_wizard.shopping.grocery_list import (
    _load_week_plan_names,
    build_grocery_list,
)

_SUSPICIOUS_NORMALIZED_RE = re.compile(
    r"\[x\]|</?br|▢|recipe serves|heat the|stir to combine",
    re.IGNORECASE,
)


@dataclass
class PipelineRunReport:
    seed: int | None
    plan_source: str
    recipe_names: list[str] = field(default_factory=list)
    grocery_item_count: int = 0
    sample_items: list[str] = field(default_factory=list)
    empty_normalize_lines: list[str] = field(default_factory=list)
    junk_lines: list[str] = field(default_factory=list)
    suspicious_normalized: list[str] = field(default_factory=list)
    merged_grocery_items: list[str] = field(default_factory=list)
    missing_recipes: list[str] = field(default_factory=list)
    recipes_without_ingredients: list[str] = field(default_factory=list)
    suspicious_stored_ingredients: list[str] = field(default_factory=list)


@dataclass
class PipelineValidationReport:
    runs: list[PipelineRunReport] = field(default_factory=list)
    total_recipes_in_db: int = 0


def _resolve_plan_names(
    db: NotionRecipesDB,
    *,
    meals: int,
    seed: int | None,
    week_plan_path: Path,
    use_saved_week_plan: bool = True,
) -> tuple[list[str], str]:
    if use_saved_week_plan:
        saved = _load_week_plan_names(week_plan_path)
        if saved:
            return saved, f"week plan ({week_plan_path})"

    if seed is not None:
        random.seed(seed)

    all_recipes = db.query_recipes()
    filters = default_filters(db.schema.all_columns)
    names = suggest_meals(
        all_recipes,
        meals=meals,
        filters=filters,
        schema_columns=db.schema.all_columns,
    )
    source = f"suggest_meals (meals={meals}"
    if seed is not None:
        source += f", seed={seed}"
    source += ")"
    return names, source


def _analyze_recipe_ingredients(
    recipe: Recipe,
    report: PipelineRunReport,
) -> list[str]:
    if not recipe.ingredients or not recipe.ingredients.strip():
        report.recipes_without_ingredients.append(recipe.name)
        return []

    if looks_suspicious_ingredients(recipe.ingredients):
        report.suspicious_stored_ingredients.append(recipe.name)

    lines, _ = parse_ingredients_text(recipe.ingredients)
    for line in lines:
        if is_junk_ingredient(line):
            report.junk_lines.append(f"{recipe.name}: {line}")
        normalized = normalize_ingredient(line)
        if not normalized:
            report.empty_normalize_lines.append(f"{recipe.name}: {line}")
        elif _SUSPICIOUS_NORMALIZED_RE.search(normalized):
            report.suspicious_normalized.append(f"{recipe.name}: {line} → {normalized}")
    return lines


def run_pipeline_validation(
    db: NotionRecipesDB,
    *,
    meals: int | None = None,
    seeds: list[int | None] | None = None,
    week_plan_path: Path = WEEK_PLAN_PATH,
    use_saved_week_plan: bool = True,
) -> PipelineValidationReport:
    """Run meal-plan → grocery-list validation for one or more random seeds."""
    config = load_config()
    meal_count = meals if meals is not None else config.default_meals
    run_seeds = seeds if seeds is not None else [None]

    all_recipes = db.query_recipes()
    recipes_by_name = {recipe.name.lower(): recipe for recipe in all_recipes}
    validation = PipelineValidationReport(total_recipes_in_db=len(all_recipes))

    for seed in run_seeds:
        plan_names, plan_source = _resolve_plan_names(
            db,
            meals=meal_count,
            seed=seed,
            week_plan_path=week_plan_path,
            use_saved_week_plan=use_saved_week_plan,
        )
        run = PipelineRunReport(seed=seed, plan_source=plan_source, recipe_names=plan_names)

        for name in plan_names:
            recipe = recipes_by_name.get(name.lower())
            if recipe is None:
                run.missing_recipes.append(name)
                continue
            _analyze_recipe_ingredients(recipe, run)

        grocery_items, _, _ = build_grocery_list(
            db,
            recipe_names=plan_names,
            include_recurring_weekly_items=False,
            exclude_pantry=True,
        )
        run.grocery_item_count = len(grocery_items)
        run.sample_items = grocery_items[:15]
        run.merged_grocery_items = [
            item for item in grocery_items if looks_like_merged_ingredient_line(item)
        ]
        validation.runs.append(run)

    return validation


def format_pipeline_report(report: PipelineValidationReport) -> str:
    lines = [
        "Pipeline validation report",
        f"Recipes in Notion: {report.total_recipes_in_db}",
        f"Runs: {len(report.runs)}",
        "",
    ]

    for index, run in enumerate(report.runs, start=1):
        lines.extend(
            [
                f"--- Run {index} ---",
                f"Plan source: {run.plan_source}",
                f"Recipes ({len(run.recipe_names)}): {', '.join(run.recipe_names)}",
                f"Grocery items: {run.grocery_item_count}",
                "",
                "Sample grocery items:",
            ]
        )
        if run.sample_items:
            lines.extend(f"  - {item}" for item in run.sample_items)
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"Missing from Notion ({len(run.missing_recipes)}):")
        if run.missing_recipes:
            lines.extend(f"  - {name}" for name in run.missing_recipes)
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"Recipes without ingredients ({len(run.recipes_without_ingredients)}):")
        if run.recipes_without_ingredients:
            lines.extend(f"  - {name}" for name in run.recipes_without_ingredients)
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(
            f"Suspicious stored ingredient text ({len(run.suspicious_stored_ingredients)}):"
        )
        if run.suspicious_stored_ingredients:
            lines.extend(f"  - {name}" for name in run.suspicious_stored_ingredients)
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"Empty-normalize ingredient lines ({len(run.empty_normalize_lines)}):")
        if run.empty_normalize_lines:
            lines.extend(f"  - {entry}" for entry in run.empty_normalize_lines[:25])
            if len(run.empty_normalize_lines) > 25:
                lines.append(f"  ... and {len(run.empty_normalize_lines) - 25} more")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"Junk lines in stored ingredients ({len(run.junk_lines)}):")
        if run.junk_lines:
            lines.extend(f"  - {entry}" for entry in run.junk_lines[:15])
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"Suspicious normalized names ({len(run.suspicious_normalized)}):")
        if run.suspicious_normalized:
            lines.extend(f"  - {entry}" for entry in run.suspicious_normalized[:15])
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"Merged grocery list items ({len(run.merged_grocery_items)}):")
        if run.merged_grocery_items:
            lines.extend(f"  - {item}" for item in run.merged_grocery_items[:25])
        else:
            lines.append("  (none)")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def validate_and_save_report(
    output_path: Path,
    *,
    seeds: list[int | None] | None = None,
    meals: int | None = None,
    week_plan_path: Path = WEEK_PLAN_PATH,
    use_saved_week_plan: bool = True,
) -> PipelineValidationReport:
    config = load_config()
    db = NotionRecipesDB(config)
    report = run_pipeline_validation(
        db,
        meals=meals,
        seeds=seeds,
        week_plan_path=week_plan_path,
        use_saved_week_plan=use_saved_week_plan,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_pipeline_report(report), encoding="utf-8")
    return report
