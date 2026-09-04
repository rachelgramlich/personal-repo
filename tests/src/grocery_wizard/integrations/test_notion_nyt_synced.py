"""Tests for NYT synced checkbox column detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.grocery_wizard.config import Config
from src.grocery_wizard.integrations.notion import (
    DEFAULT_NYT_SYNCED_COLUMN,
    ColumnInfo,
    DatabaseSchema,
    NotionRecipesDB,
)


def _schema_with_nyt_checkbox() -> DatabaseSchema:
    return DatabaseSchema(
        name_column="Name",
        link_column="Link",
        ingredients_column="Ingredients",
        filter_columns=[],
        checkbox_columns=[
            ColumnInfo(name=DEFAULT_NYT_SYNCED_COLUMN, type="checkbox"),
        ],
        all_columns={
            "Name": ColumnInfo(name="Name", type="title"),
            "Link": ColumnInfo(name="Link", type="url"),
            DEFAULT_NYT_SYNCED_COLUMN: ColumnInfo(
                name=DEFAULT_NYT_SYNCED_COLUMN,
                type="checkbox",
            ),
        },
    )


def test_nyt_synced_column_name_detects_checkbox() -> None:
    db = NotionRecipesDB.__new__(NotionRecipesDB)
    db._config = Config(
        notion_api_key="key",
        notion_database_id="db",
    )
    db.schema = _schema_with_nyt_checkbox()

    assert db.nyt_synced_column_name() == DEFAULT_NYT_SYNCED_COLUMN


def test_nyt_synced_column_name_missing_returns_none() -> None:
    db = NotionRecipesDB.__new__(NotionRecipesDB)
    db._config = Config(
        notion_api_key="key",
        notion_database_id="db",
    )
    db.schema = DatabaseSchema(
        name_column="Name",
        link_column="Link",
        ingredients_column=None,
        filter_columns=[],
        checkbox_columns=[],
        all_columns={
            "Name": ColumnInfo(name="Name", type="title"),
            "Link": ColumnInfo(name="Link", type="url"),
        },
    )

    assert db.nyt_synced_column_name() is None


def test_add_prefetched_recipes_sets_nyt_checkbox() -> None:
    from src.grocery_wizard.recipes.add_recipe import add_prefetched_recipes

    db = MagicMock()
    db.schema.name_column = "Name"
    db.schema.link_column = "Link"
    db.schema.ingredients_column = "Ingredients"
    db.schema.filter_columns = []
    db.nyt_synced_column_name.return_value = DEFAULT_NYT_SYNCED_COLUMN
    db.find_by_link.return_value = None
    db.create_recipe.side_effect = lambda values: MagicMock(
        page_id="page-1",
        name=values["Name"],
    )

    add_prefetched_recipes(
        db,
        [("Cake", "https://example.com/cake", [])],
        no_confirm=True,
        include_ingredients=False,
        mark_nyt_synced=True,
    )

    field_values = db.create_recipe.call_args[0][0]
    assert field_values[DEFAULT_NYT_SYNCED_COLUMN] is True
