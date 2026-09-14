"""Weekly meal plans stored in Notion (CSV backend for tests only)."""

from __future__ import annotations

__all__ = [
    "SavedWeeklyPlan",
    "ensure_saved_weekly_plan",
    "find_matching_plan",
    "format_plan_name",
    "list_saved_plans",
    "load_plan_recipes",
    "next_plan_version",
    "normalize_recipe_names",
    "week_start_sunday",
]

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.grocery_wizard.integrations.notion import NotionRecipesDB

RECIPE_SEPARATOR = "|"
CSV_FIELDNAMES = ("date", "version", "name", "recipes")


@dataclass(frozen=True)
class SavedWeeklyPlan:
    """One saved meal plan. ``week_start`` is the Sunday that begins the plan week."""

    week_start: date
    version: int
    name: str
    recipes: tuple[str, ...]


def week_start_sunday(d: date) -> date:
    """Return the Sunday on or before ``d`` (Sunday-start weeks)."""
    days_since_sunday = (d.weekday() + 1) % 7
    return d - timedelta(days=days_since_sunday)


def format_plan_name(week_start: date, version: int) -> str:
    return f"{week_start.isoformat()}_plan_v{version}"


def normalize_recipe_names(recipe_names: list[str]) -> tuple[str, ...]:
    return tuple(name.strip() for name in recipe_names if name.strip())


def _parse_week_start(raw: str) -> date:
    return date.fromisoformat(raw.strip())


def _encode_recipes(recipes: list[str] | tuple[str, ...]) -> str:
    if isinstance(recipes, tuple):
        cleaned = list(recipes)
    else:
        cleaned = [name.strip() for name in recipes if name.strip()]
    return RECIPE_SEPARATOR.join(cleaned)


def _decode_recipes(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    return tuple(part.strip() for part in raw.split(RECIPE_SEPARATOR) if part.strip())


def _row_to_plan(row: dict[str, str]) -> SavedWeeklyPlan | None:
    try:
        version = int(row["version"])
        week_start = _parse_week_start(row["date"])
    except (KeyError, ValueError):
        return None
    name = (row.get("name") or "").strip()
    if not name:
        slug = (row.get("slug") or "").strip()
        name = slug
    if not name:
        return None
    return SavedWeeklyPlan(
        week_start=week_start,
        version=version,
        name=name,
        recipes=_decode_recipes(row.get("recipes", "")),
    )


def _list_saved_plans_csv(path: Path) -> list[SavedWeeklyPlan]:
    if not path.exists() or path.stat().st_size == 0:
        return []

    plans: list[SavedWeeklyPlan] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            plan = _row_to_plan(row)
            if plan is not None:
                plans.append(plan)

    plans.sort(key=lambda plan: (plan.week_start, plan.version), reverse=True)
    return plans


def list_saved_plans(
    *,
    path: Path | None = None,
    recipes_db: NotionRecipesDB | None = None,
) -> list[SavedWeeklyPlan]:
    """Return saved plans newest-first (by week start, then version)."""
    if path is not None:
        return _list_saved_plans_csv(path)
    from src.grocery_wizard.integrations.notion_household import NotionWeeklyPlansDB

    return NotionWeeklyPlansDB(recipes_db=recipes_db).list_plans()


def load_plan_recipes(
    plan_name: str,
    *,
    path: Path | None = None,
    recipes_db: NotionRecipesDB | None = None,
) -> list[str]:
    """Return recipe names for a saved plan name, or empty if not found."""
    if path is not None:
        for plan in _list_saved_plans_csv(path):
            if plan.name == plan_name:
                return list(plan.recipes)
        return []
    from src.grocery_wizard.integrations.notion_household import NotionWeeklyPlansDB

    return NotionWeeklyPlansDB(recipes_db=recipes_db).load_plan_recipes(plan_name)


def find_matching_plan(
    week_start: date,
    recipes: tuple[str, ...],
    *,
    path: Path | None = None,
    recipes_db: NotionRecipesDB | None = None,
) -> SavedWeeklyPlan | None:
    """Return an existing plan with the same Sunday week start and recipe list."""
    if path is not None:
        for plan in _list_saved_plans_csv(path):
            if plan.week_start == week_start and plan.recipes == recipes:
                return plan
        return None
    from src.grocery_wizard.integrations.notion_household import NotionWeeklyPlansDB

    return NotionWeeklyPlansDB(recipes_db=recipes_db).find_matching_plan(week_start, recipes)


def next_plan_version(
    week_start: date,
    *,
    path: Path | None = None,
    recipes_db: NotionRecipesDB | None = None,
) -> int:
    """Next version number for a new distinct recipe list in the given week."""
    if path is not None:
        existing = [plan for plan in _list_saved_plans_csv(path) if plan.week_start == week_start]
        return max((plan.version for plan in existing), default=0) + 1
    from src.grocery_wizard.integrations.notion_household import NotionWeeklyPlansDB

    return NotionWeeklyPlansDB(recipes_db=recipes_db).next_plan_version(week_start)


def _ensure_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()


def ensure_saved_weekly_plan(
    recipe_names: list[str],
    *,
    reference_date: date | None = None,
    path: Path | None = None,
    recipes_db: NotionRecipesDB | None = None,
) -> tuple[SavedWeeklyPlan, bool]:
    """Persist a plan when missing for this week+recipes."""
    if path is None:
        from src.grocery_wizard.integrations.notion_household import NotionWeeklyPlansDB

        return NotionWeeklyPlansDB(recipes_db=recipes_db).ensure_plan(
            recipe_names,
            reference_date=reference_date,
        )

    when = reference_date or datetime.now(tz=UTC).date()
    week_start = week_start_sunday(when)
    recipes = normalize_recipe_names(recipe_names)
    if not recipes:
        raise ValueError("recipe_names must not be empty")

    existing = find_matching_plan(week_start, recipes, path=path)
    if existing is not None:
        return existing, False

    version = next_plan_version(week_start, path=path)
    name = format_plan_name(week_start, version)
    plan = SavedWeeklyPlan(
        week_start=week_start,
        version=version,
        name=name,
        recipes=recipes,
    )
    _ensure_csv_header(path)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writerow(
            {
                "date": plan.week_start.isoformat(),
                "version": str(plan.version),
                "name": plan.name,
                "recipes": _encode_recipes(plan.recipes),
            }
        )
    return plan, True
