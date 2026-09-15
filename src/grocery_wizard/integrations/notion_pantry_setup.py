"""One-time / repeat Notion setup for the pantry database."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.grocery_wizard.config import load_config
from src.grocery_wizard.integrations.notion_household import (
    NotionPantryDB,
    resolve_pantry_aisle_column,
)
from src.grocery_wizard.integrations.notion_table import NotionDatabase
from src.grocery_wizard.shopping.store_aisles import (
    aisle_label,
    classify_aisle,
    load_store_aisles,
    pantry_aisle_section_labels,
)

_SELECT_OPTION_COLORS = (
    "default",
    "gray",
    "brown",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
    "red",
)


@dataclass(frozen=True)
class PantrySectionSyncResult:
    aisle_labels: tuple[str, ...]
    previous_type: str
    schema_updated: bool
    rows_migrated: int


@dataclass(frozen=True)
class PantryAisleRemapResult:
    rows_updated: int
    rows_unchanged: int
    by_aisle: dict[str, int]


def _merge_select_option_payloads(
    existing_prop: dict[str, Any] | None,
    labels: list[str],
) -> list[dict[str, Any]]:
    existing_by_name: dict[str, dict[str, Any]] = {}
    if existing_prop and existing_prop.get("type") == "select":
        for option in existing_prop.get("select", {}).get("options", []):
            name = str(option.get("name", "")).strip()
            if name:
                existing_by_name[name.lower()] = option

    payloads: list[dict[str, Any]] = []
    for index, label in enumerate(labels):
        prior = existing_by_name.get(label.lower())
        if prior and prior.get("id"):
            payloads.append({"id": prior["id"], "name": prior["name"]})
        else:
            payloads.append(
                {
                    "name": label,
                    "color": _SELECT_OPTION_COLORS[index % len(_SELECT_OPTION_COLORS)],
                }
            )
    return payloads


def _aisle_label_for_pantry_item(item_name: str) -> str:
    cfg = load_store_aisles()
    aisle_id = classify_aisle(item_name, config=cfg)
    return aisle_label(aisle_id, config=cfg)


def remap_pantry_aisles_from_item_names(*, dry_run: bool = False) -> PantryAisleRemapResult:
    """Set each pantry row's Aisle from ``store_aisles`` keyword classification of its name."""
    config = load_config()
    pantry = NotionPantryDB(config)
    db = NotionDatabase(config, config.notion_pantry_database_id)
    aisle_column = pantry.aisle_column

    rows_updated = 0
    rows_unchanged = 0
    by_aisle: dict[str, int] = {}

    for entry in pantry.list_entries():
        target = _aisle_label_for_pantry_item(entry.name)
        by_aisle[target] = by_aisle.get(target, 0) + 1
        current = (entry.section or "").strip()
        if current == target:
            rows_unchanged += 1
            continue
        rows_updated += 1
        if not dry_run:
            props = {**db.property_payload(aisle_column, target)}
            db.update_page(entry.page_id, props)

    return PantryAisleRemapResult(
        rows_updated=rows_updated,
        rows_unchanged=rows_unchanged,
        by_aisle=by_aisle,
    )


def sync_pantry_section_store_aisles(*, dry_run: bool = False) -> PantrySectionSyncResult:
    """Set pantry Aisle/Section select options from ``store_aisles.txt`` labels."""
    config = load_config()
    labels = pantry_aisle_section_labels()
    db = NotionDatabase(config, config.notion_pantry_database_id)
    aisle_column = resolve_pantry_aisle_column(db.column_types)
    data_source = db.retrieve_data_source()
    properties = data_source.get("properties", {})
    aisle_prop = properties.get(aisle_column)
    if aisle_prop is None:
        raise ValueError(
            f"Pantry database is missing the {aisle_column!r} property. "
            "Add an Aisle column in Notion first."
        )

    previous_type = str(aisle_prop.get("type", ""))
    option_payloads = _merge_select_option_payloads(aisle_prop, labels)
    schema_updated = False
    if not dry_run:
        db.update_data_source_properties(
            {
                aisle_column: {
                    "select": {"options": option_payloads},
                }
            }
        )
        schema_updated = True

    remap = remap_pantry_aisles_from_item_names(dry_run=dry_run)

    return PantrySectionSyncResult(
        aisle_labels=tuple(labels),
        previous_type=previous_type,
        schema_updated=schema_updated,
        rows_migrated=remap.rows_updated,
    )
