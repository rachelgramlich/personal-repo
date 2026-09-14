"""Tests for committed weekly plan CSV persistence."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.grocery_wizard.planning.saved_weekly_plans import (
    append_saved_plan,
    format_plan_name,
    list_saved_plans,
    load_plan_recipes,
    next_plan_identity,
)


def test_format_plan_name() -> None:
    assert format_plan_name(date(2026, 9, 14), 1) == "2026-09-14_plan_v1"


def test_append_and_list_saved_plans(tmp_path: Path) -> None:
    path = tmp_path / "saved_weekly_plans.csv"
    plan = append_saved_plan(["Pasta", "Curry"], plan_date=date(2026, 9, 14), path=path)

    assert plan.name == "2026-09-14_plan_v1"
    assert plan.slug == "2026-09-14_plan_v1"
    assert plan.version == 1
    assert plan.recipes == ("Pasta", "Curry")

    plans = list_saved_plans(path=path)
    assert len(plans) == 1
    assert plans[0].slug == "2026-09-14_plan_v1"


def test_next_version_same_day(tmp_path: Path) -> None:
    path = tmp_path / "saved_weekly_plans.csv"
    append_saved_plan(["A"], plan_date=date(2026, 9, 14), path=path)
    second = append_saved_plan(["B", "C"], plan_date=date(2026, 9, 14), path=path)

    assert second.version == 2
    assert second.name == "2026-09-14_plan_v2"
    assert load_plan_recipes("2026-09-14_plan_v2", path=path) == ["B", "C"]


def test_next_plan_identity_on_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "saved_weekly_plans.csv"
    version, name, slug = next_plan_identity(date(2026, 9, 14), path=path)
    assert version == 1
    assert name == slug == "2026-09-14_plan_v1"


def test_list_saved_plans_newest_first(tmp_path: Path) -> None:
    path = tmp_path / "saved_weekly_plans.csv"
    append_saved_plan(["Old"], plan_date=date(2026, 9, 1), path=path)
    append_saved_plan(["New"], plan_date=date(2026, 9, 14), path=path)

    slugs = [plan.slug for plan in list_saved_plans(path=path)]
    assert slugs == ["2026-09-14_plan_v1", "2026-09-01_plan_v1"]
