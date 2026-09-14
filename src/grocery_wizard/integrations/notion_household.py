"""Notion databases for pantry staples, recurring items, and weekly meal plans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from src.grocery_wizard.config import Config, load_config
from src.grocery_wizard.integrations.notion import NotionRecipesDB
from src.grocery_wizard.integrations.notion_table import NotionDatabase, NotionPageRow
from src.grocery_wizard.planning.saved_weekly_plans import (
    SavedWeeklyPlan,
    format_plan_name,
    normalize_recipe_names,
    week_start_sunday,
)
from src.grocery_wizard.shopping.pantry import PantrySection, parse_pantry_file_from_lines

PANTRY_NAME_COLUMN = "Name"
PANTRY_SECTION_COLUMN = "Section"
RECURRING_NAME_COLUMN = "Name"

PLAN_NAME_COLUMN = "Name"
PLAN_WEEK_START_COLUMN = "Week start"
PLAN_VERSION_COLUMN = "Version"
PLAN_RECIPES_COLUMN = "Recipes"


def _section_header(label: str | None) -> str | None:
    if not label or not str(label).strip():
        return None
    text = str(label).strip()
    if text.startswith("#"):
        return text
    return f"# --- {text} ---"


def _section_label_from_header(header: str | None) -> str | None:
    if not header:
        return None
    text = header.strip()
    if not text.startswith("#"):
        return text or None
    inner = re.sub(r"^#\s*---\s*", "", text)
    inner = re.sub(r"\s*---\s*$", "", inner)
    return inner.strip() or None


@dataclass(frozen=True)
class PantryEntry:
    page_id: str
    name: str
    section: str | None


class NotionPantryDB:
    def __init__(self, config: Config | None = None) -> None:
        cfg = config or load_config()
        db_id = cfg.notion_pantry_database_id
        if not db_id:
            raise ValueError("NOTION_PANTRY_DATABASE_ID is required")
        self._db = NotionDatabase(cfg, db_id)

    def load_item_names(self) -> set[str]:
        return {entry.name.strip().lower() for entry in self.list_entries() if entry.name.strip()}

    def list_entries(self) -> list[PantryEntry]:
        rows = self._db.query_all_pages()
        entries: list[PantryEntry] = []
        for row in rows:
            name = self._db.read(row, PANTRY_NAME_COLUMN)
            if not name or not str(name).strip():
                continue
            section = self._db.read(row, PANTRY_SECTION_COLUMN)
            entries.append(
                PantryEntry(
                    page_id=row.page_id,
                    name=str(name).strip(),
                    section=str(section).strip() if section else None,
                )
            )
        return entries

    def load_as_pantry_lines(self) -> tuple[list[str], list[PantrySection]]:
        entries = self.list_entries()
        if not entries:
            lines = [
                "# Pantry staples — one item per line.",
                "# Lines starting with # are section headers or comments.",
                "",
                "# --- Uncategorized ---",
            ]
            return lines, [PantrySection(header="# --- Uncategorized ---")]

        by_section: dict[str | None, list[PantryEntry]] = {}
        section_order: list[str | None] = []
        for entry in entries:
            key = entry.section
            if key not in by_section:
                by_section[key] = []
                section_order.append(key)
            by_section[key].append(entry)

        lines: list[str] = []
        for section_key in section_order:
            header = _section_header(section_key) or "# --- Uncategorized ---"
            lines.append(header)
            for entry in sorted(by_section[section_key], key=lambda e: e.name.lower()):
                lines.append(entry.name)
        return parse_pantry_file_from_lines(lines)

    def sync_from_lines(self, lines: list[str]) -> None:
        """Replace Notion pantry rows to match in-memory pantry file lines."""
        _, sections = parse_pantry_file_from_lines(lines)
        desired: list[tuple[str, str | None]] = []
        current_section: str | None = None
        for section in sections:
            if section.header:
                current_section = _section_label_from_header(section.header)
            for _idx, item in section.items:
                desired.append((item.strip(), current_section))

        existing = self.list_entries()
        by_name: dict[str, PantryEntry] = {e.name.strip().lower(): e for e in existing}
        seen: set[str] = set()

        for name, section in desired:
            key = name.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            entry = by_name.get(key)
            if entry is None:
                props = {
                    **self._db.property_payload(PANTRY_NAME_COLUMN, name),
                    **self._db.property_payload(PANTRY_SECTION_COLUMN, section or ""),
                }
                self._db.create_page(props)
            elif (entry.section or "") != (section or ""):
                props = {
                    **self._db.property_payload(PANTRY_SECTION_COLUMN, section or ""),
                }
                self._db.update_page(entry.page_id, props)

        for entry in existing:
            if entry.name.strip().lower() not in seen:
                self._db.archive_page(entry.page_id)

    def append_item(self, name: str, *, section: str | None = None) -> bool:
        cleaned = name.strip()
        if not cleaned:
            return False
        key = cleaned.lower()
        if any(e.name.strip().lower() == key for e in self.list_entries()):
            return False
        target_section = section
        if target_section is None:
            entries = self.list_entries()
            if entries:
                target_section = entries[-1].section
        props = {
            **self._db.property_payload(PANTRY_NAME_COLUMN, cleaned),
            **self._db.property_payload(PANTRY_SECTION_COLUMN, target_section or ""),
        }
        self._db.create_page(props)
        return True

    def remove_item_by_name(self, search: str) -> bool:
        from src.grocery_wizard.shopping.pantry import _matches_pantry_search

        lowered = search.strip()
        if not lowered:
            return False
        for entry in self.list_entries():
            if _matches_pantry_search(lowered, entry.name):
                self._db.archive_page(entry.page_id)
                return True
        return False


class NotionRecurringDB:
    def __init__(self, config: Config | None = None) -> None:
        cfg = config or load_config()
        db_id = cfg.notion_recurring_weekly_database_id
        if not db_id:
            raise ValueError("NOTION_RECURRING_WEEKLY_DATABASE_ID is required")
        self._db = NotionDatabase(cfg, db_id)

    def load_items(self) -> list[str]:
        rows = self._db.query_all_pages()
        items: list[str] = []
        for row in rows:
            name = self._db.read(row, RECURRING_NAME_COLUMN)
            if name and str(name).strip():
                items.append(str(name).strip())
        return items

    def replace_all(self, items: list[str]) -> None:
        cleaned = [item.strip() for item in items if item.strip()]
        existing = self._load_rows_by_name()
        seen: set[str] = set()
        for item in cleaned:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            if key not in existing:
                self._db.create_page(self._db.property_payload(RECURRING_NAME_COLUMN, item))
        for key, row in existing.items():
            if key not in seen:
                self._db.archive_page(row.page_id)

    def append_item(self, name: str) -> bool:
        cleaned = name.strip()
        if not cleaned:
            return False
        if any(existing.lower() == cleaned.lower() for existing in self.load_items()):
            return False
        self._db.create_page(self._db.property_payload(RECURRING_NAME_COLUMN, cleaned))
        return True

    def remove_item(self, search: str) -> bool:
        lowered = search.strip().lower()
        if not lowered:
            return False
        for row in self._load_rows_by_name().values():
            name = self._db.read(row, RECURRING_NAME_COLUMN)
            if name and str(name).strip().lower() == lowered:
                self._db.archive_page(row.page_id)
                return True
        return False

    def _load_rows_by_name(self) -> dict[str, NotionPageRow]:
        rows = self._db.query_all_pages()
        by_name: dict[str, NotionPageRow] = {}
        for row in rows:
            name = self._db.read(row, RECURRING_NAME_COLUMN)
            if name and str(name).strip():
                by_name[str(name).strip().lower()] = row
        return by_name


class NotionWeeklyPlansDB:
    def __init__(
        self,
        config: Config | None = None,
        *,
        recipes_db: NotionRecipesDB | None = None,
    ) -> None:
        cfg = config or load_config()
        db_id = cfg.notion_weekly_meal_plans_database_id
        if not db_id:
            raise ValueError("NOTION_WEEKLY_MEAL_PLANS_DATABASE_ID is required")
        self._db = NotionDatabase(cfg, db_id)
        self._recipes_db = recipes_db or NotionRecipesDB(cfg)

    def list_plans(self) -> list[SavedWeeklyPlan]:
        rows = self._db.query_all_pages()
        plans: list[SavedWeeklyPlan] = []
        recipe_names_by_id = self._recipe_names_by_page_id()
        for row in rows:
            plan = self._row_to_plan(row, recipe_names_by_id)
            if plan is not None:
                plans.append(plan)
        plans.sort(key=lambda plan: (plan.week_start, plan.version), reverse=True)
        return plans

    def load_plan_recipes(self, plan_name: str) -> list[str]:
        for plan in self.list_plans():
            if plan.name == plan_name:
                return list(plan.recipes)
        return []

    def find_matching_plan(
        self,
        week_start: date,
        recipes: tuple[str, ...],
    ) -> SavedWeeklyPlan | None:
        for plan in self.list_plans():
            if plan.week_start == week_start and plan.recipes == recipes:
                return plan
        return None

    def next_plan_version(self, week_start: date) -> int:
        existing = [plan for plan in self.list_plans() if plan.week_start == week_start]
        return max((plan.version for plan in existing), default=0) + 1

    def ensure_plan(
        self,
        recipe_names: list[str],
        *,
        reference_date: date | None = None,
    ) -> tuple[SavedWeeklyPlan, bool]:
        from datetime import UTC, datetime

        when = reference_date or datetime.now(tz=UTC).date()
        week_start = week_start_sunday(when)
        recipes = normalize_recipe_names(recipe_names)
        if not recipes:
            raise ValueError("recipe_names must not be empty")

        existing = self.find_matching_plan(week_start, recipes)
        if existing is not None:
            return existing, False

        version = self.next_plan_version(week_start)
        name = format_plan_name(week_start, version)
        relation_ids = self._recipe_page_ids_for_names(recipes)
        props = {
            **self._db.property_payload(PLAN_NAME_COLUMN, name),
            **self._db.property_payload(PLAN_WEEK_START_COLUMN, week_start.isoformat()),
            **self._db.property_payload(PLAN_VERSION_COLUMN, version),
            **self._db.property_payload(PLAN_RECIPES_COLUMN, relation_ids),
        }
        row = self._db.create_page(props)
        recipe_names_by_id = self._recipe_names_by_page_id()
        plan = self._row_to_plan(row, recipe_names_by_id)
        if plan is None:
            raise RuntimeError("Failed to read plan after Notion create")
        return plan, True

    def _row_to_plan(
        self,
        row: NotionPageRow,
        recipe_names_by_id: dict[str, str],
    ) -> SavedWeeklyPlan | None:
        name = self._db.read(row, PLAN_NAME_COLUMN)
        if not name or not str(name).strip():
            return None
        week_raw = self._db.read(row, PLAN_WEEK_START_COLUMN)
        version_raw = self._db.read(row, PLAN_VERSION_COLUMN)
        try:
            week_start = date.fromisoformat(str(week_raw).strip())
            version = int(version_raw) if version_raw is not None else 0
        except (TypeError, ValueError):
            return None
        relation_ids = self._db.read(row, PLAN_RECIPES_COLUMN) or []
        recipe_names: list[str] = []
        for page_id in relation_ids:
            recipe_name = recipe_names_by_id.get(page_id)
            if recipe_name:
                recipe_names.append(recipe_name)
        return SavedWeeklyPlan(
            week_start=week_start,
            version=version,
            name=str(name).strip(),
            recipes=tuple(recipe_names),
        )

    def _recipe_names_by_page_id(self) -> dict[str, str]:
        return {recipe.page_id: recipe.name for recipe in self._recipes_db.query_recipes()}

    def _recipe_page_ids_for_names(self, recipe_names: tuple[str, ...]) -> list[str]:
        recipes = self._recipes_db.query_recipes()
        by_name = {recipe.name.lower(): recipe.page_id for recipe in recipes}
        ids: list[str] = []
        for name in recipe_names:
            page_id = by_name.get(name.lower())
            if page_id:
                ids.append(page_id)
        return ids
