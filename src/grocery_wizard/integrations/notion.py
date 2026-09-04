"""Notion database integration for recipe storage."""

from __future__ import annotations

__all__ = ["ColumnInfo", "DatabaseSchema", "NotionRecipesDB", "Recipe"]

from dataclasses import dataclass, field
from typing import Any

from notion_client import Client

from src.grocery_wizard.config import Config


@dataclass
class ColumnInfo:
    name: str
    type: str
    options: list[str] = field(default_factory=list)


@dataclass
class DatabaseSchema:
    name_column: str
    link_column: str
    ingredients_column: str | None
    filter_columns: list[ColumnInfo]
    checkbox_columns: list[ColumnInfo]
    all_columns: dict[str, ColumnInfo]

    @property
    def review_columns(self) -> list[ColumnInfo]:
        """Select/multi-select/status columns plus checkbox columns for review."""
        return [*self.filter_columns, *self.checkbox_columns]


@dataclass
class Recipe:
    page_id: str
    name: str
    link: str | None
    ingredients: str | None
    properties: dict[str, Any]


DEFAULT_NYT_SYNCED_COLUMN = "Synced from NYT recipe box"


class NotionRecipesDB:
    def __init__(self, config: Config) -> None:
        self._client = Client(auth=config.notion_api_key)
        self._database_id = config.notion_database_id
        self._config = config
        self._data_source_id = self._resolve_data_source_id()
        self.schema = self._load_schema()

    def _resolve_data_source_id(self) -> str:
        """Resolve the data source that holds column schema (Notion API 2025+)."""
        db = self._client.databases.retrieve(database_id=self._database_id)
        data_sources = db.get("data_sources", [])
        if not data_sources:
            raise ValueError(f"No data sources found for Notion database {self._database_id}")
        if len(data_sources) == 1:
            return data_sources[0]["id"]

        for ds in data_sources:
            detail = self._client.data_sources.retrieve(data_source_id=ds["id"])
            if "Link" in detail.get("properties", {}):
                return ds["id"]
        return data_sources[0]["id"]

    def _load_schema(self) -> DatabaseSchema:
        ds = self._client.data_sources.retrieve(data_source_id=self._data_source_id)
        properties = ds.get("properties", {})

        all_columns: dict[str, ColumnInfo] = {}
        title_columns: list[str] = []
        url_columns: list[str] = []
        text_columns: list[str] = []
        filter_columns: list[ColumnInfo] = []
        checkbox_columns: list[ColumnInfo] = []

        for name, prop in properties.items():
            prop_type = prop.get("type", "")
            options = _extract_options(prop, prop_type)
            all_columns[name] = ColumnInfo(name=name, type=prop_type, options=options)

            if prop_type == "title":
                title_columns.append(name)
            elif prop_type == "url":
                url_columns.append(name)
            elif prop_type in ("rich_text", "text"):
                text_columns.append(name)
            elif prop_type in ("select", "multi_select", "status"):
                filter_columns.append(all_columns[name])
            elif prop_type == "checkbox":
                checkbox_columns.append(all_columns[name])

        name_column = self._config.name_column or (title_columns[0] if title_columns else "Name")
        link_column = self._resolve_link_column(url_columns, all_columns)
        ingredients_column = self._resolve_ingredients_column(text_columns, all_columns)

        return DatabaseSchema(
            name_column=name_column,
            link_column=link_column,
            ingredients_column=ingredients_column,
            filter_columns=filter_columns,
            checkbox_columns=checkbox_columns,
            all_columns=all_columns,
        )

    def _resolve_link_column(
        self,
        url_columns: list[str],
        all_columns: dict[str, ColumnInfo],
    ) -> str:
        if self._config.link_column:
            return self._config.link_column
        if "Link" in url_columns:
            return "Link"
        if "Link" in all_columns:
            return "Link"
        if len(url_columns) == 1:
            return url_columns[0]
        if not url_columns:
            raise ValueError("No URL column found in Notion database")
        raise ValueError("Multiple URL columns found; set GROCERY_WIZARD_LINK_COLUMN in .env")

    def _resolve_ingredients_column(
        self,
        text_columns: list[str],
        all_columns: dict[str, ColumnInfo],
    ) -> str | None:
        if self._config.ingredients_column:
            return self._config.ingredients_column
        if "Ingredients" in text_columns:
            return "Ingredients"
        if "Ingredients" in all_columns:
            return "Ingredients"
        return None

    def nyt_synced_column_name(self) -> str | None:
        """Return the NYT sync checkbox column if it exists in the database."""
        name = self._config.nyt_synced_column or DEFAULT_NYT_SYNCED_COLUMN
        column = self.schema.all_columns.get(name)
        if column and column.type == "checkbox":
            return name
        return None

    def query_recipes(self) -> list[Recipe]:
        pages: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            response = self._client.data_sources.query(
                data_source_id=self._data_source_id,
                start_cursor=cursor,
            )
            pages.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        return [self._page_to_recipe(page) for page in pages]

    def find_by_link(self, url: str) -> Recipe | None:
        for recipe in self.query_recipes():
            if recipe.link and recipe.link.rstrip("/") == url.rstrip("/"):
                return recipe
        return None

    def create_recipe(self, field_values: dict[str, Any]) -> Recipe:
        properties = {
            name: self._to_notion_property(name, value)
            for name, value in field_values.items()
            if value is not None and value not in ("", [])
        }
        page = self._client.pages.create(
            parent={"database_id": self._database_id},
            properties=properties,
        )
        return self._page_to_recipe(page)

    def update_recipe(self, page_id: str, field_values: dict[str, Any]) -> Recipe:
        properties = {
            name: self._to_notion_property(name, value)
            for name, value in field_values.items()
            if value is not None
        }
        page = self._client.pages.update(page_id=page_id, properties=properties)
        return self._page_to_recipe(page)

    def get_select_options(self, column_name: str) -> list[str]:
        column = self.schema.all_columns.get(column_name)
        return column.options if column else []

    def _page_to_recipe(self, page: dict[str, Any]) -> Recipe:
        props = page.get("properties", {})
        schema = self.schema

        return Recipe(
            page_id=page["id"],
            name=_read_property(props.get(schema.name_column)),
            link=_read_property(props.get(schema.link_column)),
            ingredients=(
                _read_property(props.get(schema.ingredients_column))
                if schema.ingredients_column
                else None
            ),
            properties={name: _read_property(prop) for name, prop in props.items()},
        )

    def _to_notion_property(self, column_name: str, value: Any) -> dict[str, Any]:
        column = self.schema.all_columns.get(column_name)
        if column is None:
            raise ValueError(f"Unknown column: {column_name}")

        if column.type == "title":
            return {"title": [{"text": {"content": str(value)}}]}
        if column.type == "url":
            return {"url": str(value)}
        if column.type in ("rich_text", "text"):
            return {"rich_text": [{"text": {"content": str(value)}}]}
        if column.type == "select":
            return {"select": {"name": str(value)}}
        if column.type == "multi_select":
            values = value if isinstance(value, list) else [value]
            return {"multi_select": [{"name": str(v)} for v in values]}
        if column.type == "status":
            return {"status": {"name": str(value)}}
        if column.type == "checkbox":
            return {"checkbox": bool(value)}
        if column.type == "number":
            return {"number": float(value)}
        raise ValueError(f"Unsupported column type for {column_name}: {column.type}")


def _extract_options(prop: dict[str, Any], prop_type: str) -> list[str]:
    if prop_type == "select":
        return [opt["name"] for opt in prop.get("select", {}).get("options", [])]
    if prop_type == "multi_select":
        return [opt["name"] for opt in prop.get("multi_select", {}).get("options", [])]
    if prop_type == "status":
        return [opt["name"] for opt in prop.get("status", {}).get("options", [])]
    return []


def _read_property(prop: dict[str, Any] | None) -> Any:
    if not prop:
        return None

    prop_type = prop.get("type")
    if prop_type == "title":
        texts = prop.get("title", [])
        return "".join(item.get("plain_text", "") for item in texts) or None
    if prop_type in ("rich_text", "text"):
        texts = prop.get("rich_text", [])
        return "".join(item.get("plain_text", "") for item in texts) or None
    if prop_type == "url":
        return prop.get("url")
    if prop_type == "select":
        selected = prop.get("select")
        return selected.get("name") if selected else None
    if prop_type == "multi_select":
        return [item.get("name", "") for item in prop.get("multi_select", [])]
    if prop_type == "status":
        status = prop.get("status")
        return status.get("name") if status else None
    if prop_type == "checkbox":
        return prop.get("checkbox")
    if prop_type == "number":
        return prop.get("number")
    return None
