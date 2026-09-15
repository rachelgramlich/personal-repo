"""Tests for NotionRecipesDB.find_by_link filtered queries."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.grocery_wizard.config import Config
from src.grocery_wizard.integrations.notion import ColumnInfo, DatabaseSchema, NotionRecipesDB


def _schema(*, link_type: str = "url") -> DatabaseSchema:
    return DatabaseSchema(
        name_column="Name",
        link_column="Link",
        ingredients_column="Ingredients",
        filter_columns=[],
        checkbox_columns=[],
        all_columns={
            "Name": ColumnInfo(name="Name", type="title"),
            "Link": ColumnInfo(name="Link", type=link_type),
            "Ingredients": ColumnInfo(name="Ingredients", type="rich_text"),
        },
    )


def _minimal_db(*, link_type: str = "url") -> NotionRecipesDB:
    config = Config.model_construct(
        notion_api_key="secret",
        notion_recipe_database_id="db-id",
        notion_pantry_database_id="pantry-id",
        notion_recurring_weekly_database_id="recurring-id",
        notion_weekly_meal_plans_database_id="plans-id",
    )
    db = NotionRecipesDB.__new__(NotionRecipesDB)
    db._client = MagicMock()
    db._database_id = "db-id"
    db._config = config
    db._data_source_id = "ds-id"
    db.schema = _schema(link_type=link_type)
    return db


def test_find_by_link_uses_notion_url_filter() -> None:
    db = _minimal_db()
    db._client.data_sources.query.return_value = {
        "results": [
            {
                "id": "page-1",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Soup"}]},
                    "Link": {"type": "url", "url": "https://example.com/soup"},
                    "Ingredients": {"type": "rich_text", "rich_text": []},
                },
            }
        ]
    }

    found = db.find_by_link("https://example.com/soup/")

    assert found is not None
    assert found.name == "Soup"
    db._client.data_sources.query.assert_called_once_with(
        data_source_id="ds-id",
        filter={"property": "Link", "url": {"equals": "https://example.com/soup"}},
    )
    db.query_recipes = MagicMock()  # type: ignore[method-assign]
    assert db.query_recipes.call_count == 0
