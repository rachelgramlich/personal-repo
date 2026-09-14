"""Committed weekly meal plans (recipe selections) stored in repo CSV."""

from __future__ import annotations

__all__ = [
    "SavedWeeklyPlan",
    "append_saved_plan",
    "format_plan_name",
    "list_saved_plans",
    "load_plan_recipes",
    "next_plan_identity",
]

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from src.grocery_wizard.config import SAVED_WEEKLY_PLANS_PATH

RECIPE_SEPARATOR = "|"
CSV_FIELDNAMES = ("date", "version", "name", "slug", "recipes")


@dataclass(frozen=True)
class SavedWeeklyPlan:
    plan_date: date
    version: int
    name: str
    slug: str
    recipes: tuple[str, ...]


def format_plan_name(plan_date: date, version: int) -> str:
    return f"{plan_date.isoformat()}_plan_v{version}"


def _parse_plan_date(raw: str) -> date:
    return date.fromisoformat(raw.strip())


def _encode_recipes(recipes: list[str]) -> str:
    cleaned = [name.strip() for name in recipes if name.strip()]
    return RECIPE_SEPARATOR.join(cleaned)


def _decode_recipes(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    return tuple(part.strip() for part in raw.split(RECIPE_SEPARATOR) if part.strip())


def _row_to_plan(row: dict[str, str]) -> SavedWeeklyPlan | None:
    try:
        version = int(row["version"])
        plan_date = _parse_plan_date(row["date"])
    except (KeyError, ValueError):
        return None
    slug = (row.get("slug") or "").strip()
    name = (row.get("name") or slug).strip()
    if not slug:
        return None
    return SavedWeeklyPlan(
        plan_date=plan_date,
        version=version,
        name=name,
        slug=slug,
        recipes=_decode_recipes(row.get("recipes", "")),
    )


def list_saved_plans(*, path: Path = SAVED_WEEKLY_PLANS_PATH) -> list[SavedWeeklyPlan]:
    """Return saved plans newest-first (by date, then version)."""
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

    plans.sort(key=lambda plan: (plan.plan_date, plan.version), reverse=True)
    return plans


def load_plan_recipes(slug: str, *, path: Path = SAVED_WEEKLY_PLANS_PATH) -> list[str]:
    """Return recipe names for a saved plan slug, or empty if not found."""
    for plan in list_saved_plans(path=path):
        if plan.slug == slug:
            return list(plan.recipes)
    return []


def next_plan_identity(
    plan_date: date | None = None,
    *,
    path: Path = SAVED_WEEKLY_PLANS_PATH,
) -> tuple[int, str, str]:
    """Return (version, name, slug) for the next plan on the given date."""
    when = plan_date or datetime.now(tz=UTC).date()
    existing = [plan for plan in list_saved_plans(path=path) if plan.plan_date == when]
    version = max((plan.version for plan in existing), default=0) + 1
    name = format_plan_name(when, version)
    return version, name, name


def _ensure_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()


def append_saved_plan(
    recipe_names: list[str],
    *,
    plan_date: date | None = None,
    path: Path = SAVED_WEEKLY_PLANS_PATH,
) -> SavedWeeklyPlan:
    """Append a new saved weekly plan row and return the stored record."""
    when = plan_date or datetime.now(tz=UTC).date()
    version, name, slug = next_plan_identity(when, path=path)
    plan = SavedWeeklyPlan(
        plan_date=when,
        version=version,
        name=name,
        slug=slug,
        recipes=tuple(name.strip() for name in recipe_names if name.strip()),
    )
    _ensure_csv_header(path)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writerow(
            {
                "date": plan.plan_date.isoformat(),
                "version": str(plan.version),
                "name": plan.name,
                "slug": plan.slug,
                "recipes": _encode_recipes(list(plan.recipes)),
            }
        )
    return plan
