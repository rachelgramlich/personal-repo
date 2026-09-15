"""Generic Notion database CRUD helpers (simple title + property rows)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from notion_client import Client

from src.grocery_wizard.config import Config

__all__ = [
    "NotionDatabase",
    "NotionPageRow",
    "read_notion_property",
    "write_notion_property",
]


@dataclass(frozen=True)
class NotionPageRow:
    page_id: str
    properties: dict[str, Any]


class NotionDatabase:
    """Minimal wrapper around a Notion database / data source."""

    def __init__(self, config: Config, database_id: str) -> None:
        self._client = Client(auth=config.notion_api_key)
        self._database_id = database_id
        self._data_source_id = self._resolve_data_source_id()
        self.column_types = self._load_column_types()

    @property
    def data_source_id(self) -> str:
        return self._data_source_id

    def _resolve_data_source_id(self) -> str:
        db = self._client.databases.retrieve(database_id=self._database_id)
        data_sources = db.get("data_sources", [])
        if not data_sources:
            raise ValueError(f"No data sources found for Notion database {self._database_id}")
        if len(data_sources) == 1:
            return data_sources[0]["id"]
        return data_sources[0]["id"]

    def _load_column_types(self) -> dict[str, str]:
        ds = self._client.data_sources.retrieve(data_source_id=self._data_source_id)
        properties = ds.get("properties", {})
        return {name: prop.get("type", "") for name, prop in properties.items()}

    def query_all_pages(self) -> list[NotionPageRow]:
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
        return [
            NotionPageRow(page_id=page["id"], properties=page.get("properties", {}))
            for page in pages
        ]

    def create_page(self, properties: dict[str, Any]) -> NotionPageRow:
        page = self._client.pages.create(
            parent={"database_id": self._database_id},
            properties=properties,
        )
        return NotionPageRow(page_id=page["id"], properties=page.get("properties", {}))

    def update_page(self, page_id: str, properties: dict[str, Any]) -> NotionPageRow:
        page = self._client.pages.update(page_id=page_id, properties=properties)
        return NotionPageRow(page_id=page["id"], properties=page.get("properties", {}))

    def archive_page(self, page_id: str) -> None:
        self._client.pages.update(page_id=page_id, archived=True)

    def property_payload(self, column_name: str, value: Any) -> dict[str, Any]:
        column_type = self.column_types.get(column_name)
        if column_type is None:
            raise ValueError(f"Unknown column: {column_name}")
        return {column_name: write_notion_property(column_type, value)}

    def read(self, row: NotionPageRow, column_name: str) -> Any:
        column_type = self.column_types.get(column_name, "")
        return read_notion_property(row.properties.get(column_name), column_type)

    def retrieve_data_source(self) -> dict[str, Any]:
        return self._client.data_sources.retrieve(data_source_id=self._data_source_id)

    def update_data_source_properties(self, properties: dict[str, Any]) -> dict[str, Any]:
        updated = self._client.data_sources.update(
            data_source_id=self._data_source_id,
            properties=properties,
        )
        self.column_types = self._load_column_types()
        return updated


def read_notion_property(prop: dict[str, Any] | None, prop_type: str) -> Any:
    if not prop:
        return None
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
    if prop_type == "date":
        date_val = prop.get("date")
        if not date_val:
            return None
        return date_val.get("start")
    if prop_type == "relation":
        return [item.get("id") for item in prop.get("relation", []) if item.get("id")]
    return None


def write_notion_property(prop_type: str, value: Any) -> dict[str, Any]:
    if prop_type == "title":
        return {"title": [{"text": {"content": str(value)}}]}
    if prop_type in ("rich_text", "text"):
        if value is None or value == "":
            return {"rich_text": []}
        return {"rich_text": [{"text": {"content": str(value)}}]}
    if prop_type == "url":
        return {"url": str(value) if value else None}
    if prop_type == "select":
        return {"select": {"name": str(value)}}
    if prop_type == "multi_select":
        values = value if isinstance(value, list) else [value]
        return {"multi_select": [{"name": str(v)} for v in values]}
    if prop_type == "status":
        return {"status": {"name": str(value)}}
    if prop_type == "checkbox":
        return {"checkbox": bool(value)}
    if prop_type == "number":
        return {"number": float(value) if value is not None else None}
    if prop_type == "date":
        if value is None:
            return {"date": None}
        return {"date": {"start": str(value)}}
    if prop_type == "relation":
        ids = value if isinstance(value, list) else []
        return {"relation": [{"id": page_id} for page_id in ids]}
    raise ValueError(f"Unsupported property type: {prop_type}")
