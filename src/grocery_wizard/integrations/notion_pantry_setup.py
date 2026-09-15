"""One-time / repeat Notion setup for the pantry database."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.grocery_wizard.config import load_config
from src.grocery_wizard.integrations.notion_household import (
    PANTRY_SECTION_COLUMN,
    NotionPantryDB,
)
from src.grocery_wizard.integrations.notion_table import NotionDatabase
from src.grocery_wizard.shopping.store_aisles import (
    canonical_pantry_section_label,
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


def sync_pantry_section_store_aisles(*, dry_run: bool = False) -> PantrySectionSyncResult:
    """Set pantry ``Section`` to a select whose options match ``store_aisles.txt`` labels."""
    config = load_config()
    labels = pantry_aisle_section_labels()
    db = NotionDatabase(config, config.notion_pantry_database_id)
    data_source = db.retrieve_data_source()
    properties = data_source.get("properties", {})
    section_prop = properties.get(PANTRY_SECTION_COLUMN)
    if section_prop is None:
        raise ValueError(
            f"Pantry database is missing the {PANTRY_SECTION_COLUMN!r} property. "
            "Add a Section column in Notion first."
        )

    previous_type = str(section_prop.get("type", ""))
    option_payloads = _merge_select_option_payloads(section_prop, labels)
    schema_updated = False
    if not dry_run:
        db.update_data_source_properties(
            {
                PANTRY_SECTION_COLUMN: {
                    "select": {"options": option_payloads},
                }
            }
        )
        schema_updated = True

    rows_migrated = 0
    pantry = NotionPantryDB(config)
    for entry in pantry.list_entries():
        target = canonical_pantry_section_label(entry.section)
        current = (entry.section or "").strip()
        if current == target:
            continue
        rows_migrated += 1
        if not dry_run:
            props = {
                **db.property_payload(PANTRY_SECTION_COLUMN, target),
            }
            db.update_page(entry.page_id, props)

    return PantrySectionSyncResult(
        aisle_labels=tuple(labels),
        previous_type=previous_type,
        schema_updated=schema_updated,
        rows_migrated=rows_migrated,
    )
