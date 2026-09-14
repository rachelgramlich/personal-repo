"""Tests for committed weekly plan CSV persistence."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.grocery_wizard.planning.saved_weekly_plans import (
    ensure_saved_weekly_plan,
    format_plan_name,
    list_saved_plans,
    load_plan_recipes,
    next_plan_version,
    week_start_sunday,
)


def test_format_plan_name() -> None:
    assert format_plan_name(date(2026, 9, 13), 1) == "2026-09-13_plan_v1"


def test_week_start_sunday() -> None:
    assert week_start_sunday(date(2026, 9, 13)) == date(2026, 9, 13)  # Sunday
    assert week_start_sunday(date(2026, 9, 14)) == date(2026, 9, 13)  # Monday
    assert week_start_sunday(date(2026, 9, 15)) == date(2026, 9, 13)  # Tuesday


def test_today_and_yesterday_share_week_start() -> None:
    monday = date(2026, 9, 14)
    sunday = date(2026, 9, 13)
    assert week_start_sunday(monday) == week_start_sunday(sunday)


def test_ensure_saved_plan_uses_week_start_in_csv(tmp_path: Path) -> None:
    path = tmp_path / "saved_weekly_plans.csv"
    plan, created = ensure_saved_weekly_plan(
        ["Pasta", "Curry"],
        reference_date=date(2026, 9, 14),
        path=path,
    )

    assert created is True
    assert plan.week_start == date(2026, 9, 13)
    assert plan.name == "2026-09-13_plan_v1"
    assert plan.slug == "2026-09-13_plan_v1"
    assert plan.recipes == ("Pasta", "Curry")


def test_ensure_saved_plan_dedupes_same_week_and_recipes(tmp_path: Path) -> None:
    path = tmp_path / "saved_weekly_plans.csv"
    first, created_first = ensure_saved_weekly_plan(
        ["A"],
        reference_date=date(2026, 9, 14),
        path=path,
    )
    second, created_second = ensure_saved_weekly_plan(
        ["A"],
        reference_date=date(2026, 9, 15),
        path=path,
    )

    assert created_first is True
    assert created_second is False
    assert first.slug == second.slug
    assert len(list_saved_plans(path=path)) == 1


def test_different_recipes_same_week_get_next_version(tmp_path: Path) -> None:
    path = tmp_path / "saved_weekly_plans.csv"
    ensure_saved_weekly_plan(["A"], reference_date=date(2026, 9, 14), path=path)
    second, created = ensure_saved_weekly_plan(["B", "C"], reference_date=date(2026, 9, 14), path=path)

    assert created is True
    assert second.version == 2
    assert second.name == "2026-09-13_plan_v2"
    assert load_plan_recipes("2026-09-13_plan_v2", path=path) == ["B", "C"]
    assert load_plan_recipes("2026-09-13_plan_v1", path=path) == ["A"]
    assert len(list_saved_plans(path=path)) == 2


def test_next_plan_version_on_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "saved_weekly_plans.csv"
    assert next_plan_version(date(2026, 9, 13), path=path) == 1


def test_list_saved_plans_newest_first(tmp_path: Path) -> None:
    path = tmp_path / "saved_weekly_plans.csv"
    ensure_saved_weekly_plan(["Old"], reference_date=date(2026, 9, 1), path=path)
    ensure_saved_weekly_plan(["New"], reference_date=date(2026, 9, 14), path=path)

    slugs = [plan.slug for plan in list_saved_plans(path=path)]
    assert slugs == ["2026-09-13_plan_v1", "2026-08-30_plan_v1"]
