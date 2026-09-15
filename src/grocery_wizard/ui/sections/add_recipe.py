"""Add-recipe tab."""

from __future__ import annotations

import streamlit as st

from src.grocery_wizard.ingredients.sync import prepare_ingredients_for_notion
from src.grocery_wizard.integrations.notion import (
    DatabaseSchema,
    NotionFieldValues,
    NotionRecipesDB,
)
from src.grocery_wizard.recipes.classify import classify_recipe
from src.grocery_wizard.recipes.scraper import ScrapeError, ingredients_to_text, scrape_recipe
from src.grocery_wizard.recipes.weeknight import DEFAULT_WEEKNIGHT_COLUMN
from src.grocery_wizard.ui.db_access import get_db
from src.grocery_wizard.ui.notion_cache import invalidate_notion_cache


def render_add_recipe() -> None:
    st.subheader("Add Recipe")
    st.caption("Paste a link to pull in name and ingredients, then save to Notion.")

    db = get_db()
    schema = db.schema

    urls_text = st.text_area(
        "Recipe URL",
        placeholder="https://example.com/my-recipe",
        height=80,
        key="add_recipe_urls",
    )
    if st.button("Add recipe", type="primary"):
        urls = [line.strip() for line in urls_text.splitlines() if line.strip()]
        if not urls:
            st.warning("Paste a recipe URL first.")
        else:
            st.session_state["preview_recipes"] = _preview_recipes(db, urls)

    with st.expander("Type it in myself", expanded=False):
        if st.button("Start blank recipe"):
            st.session_state["preview_recipes"] = [
                {
                    "status": "manual",
                    "url": "",
                    "fields": _base_recipe_fields(schema),
                }
            ]

    previews = st.session_state.get("preview_recipes", [])
    for index, preview in enumerate(previews):
        if preview.get("status") == "duplicate":
            st.info(f"Already in Notion: {preview['name']} ({preview['url']})")
            continue
        if preview.get("status") == "saved":
            st.success(f"Saved to Notion: {preview.get('saved_name', 'Recipe')}")
            continue

        _render_recipe_review(db, schema, preview, index)


def _ordered_recipe_field_names(schema: DatabaseSchema) -> list[str]:
    names = [schema.name_column, schema.link_column]
    if schema.ingredients_column:
        names.append(schema.ingredients_column)
    names.extend(col.name for col in schema.review_columns)
    return names


def _guess_recipe_name_from_url(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", maxsplit=1)[-1]
    slug = slug.split("?")[0]
    if not slug or slug.startswith("http"):
        return ""
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _base_recipe_fields(
    schema: DatabaseSchema,
    *,
    url: str = "",
    name: str = "",
    ingredients: str = "",
    inferred: NotionFieldValues | None = None,
) -> NotionFieldValues:
    fields: NotionFieldValues = {
        schema.name_column: name,
        schema.link_column: url,
    }
    if schema.ingredients_column:
        fields[schema.ingredients_column] = ingredients
    if inferred:
        fields.update(inferred)
    for col in schema.checkbox_columns:
        fields.setdefault(col.name, False)
    return fields


def _render_recipe_review(
    db: NotionRecipesDB,
    schema: DatabaseSchema,
    preview: dict[str, object],
    index: int,
) -> None:
    status = preview.get("status", "ready")
    fields = preview["fields"]
    recipe_name = fields.get(schema.name_column) or "New recipe"

    if preview.get("error"):
        st.warning(preview["error"])

    title = "Review before saving"
    if status == "manual" and not fields.get(schema.name_column):
        title = "Add recipe details"
    elif status == "ready":
        title = f"Review: {recipe_name}"

    with st.expander(title, expanded=True):
        edited = _render_recipe_field_editors(schema, fields, key_prefix=f"recipe_{index}")

        if st.button("Save to Notion", key=f"save_{index}", type="primary"):
            cleaned = {key: value for key, value in edited.items() if value not in (None, "", [])}
            name = cleaned.get(schema.name_column, "").strip()
            if not name:
                st.warning("Add a recipe name before saving.")
                return
            if schema.ingredients_column and not cleaned.get(schema.ingredients_column, "").strip():
                st.warning("Add ingredients before saving (one per line).")
                return

            if schema.ingredients_column:
                source_url = cleaned.get(schema.link_column) or preview.get("url")
                cleaned[schema.ingredients_column] = prepare_ingredients_for_notion(
                    cleaned[schema.ingredients_column],
                    source_url=source_url,
                )
                if not cleaned[schema.ingredients_column].strip():
                    st.warning("Add ingredients before saving (one per line).")
                    return

            recipe = db.create_recipe(cleaned)
            invalidate_notion_cache()
            preview["status"] = "saved"
            preview["saved_name"] = recipe.name
            st.rerun()


def _render_recipe_field_editors(
    schema: DatabaseSchema,
    fields: NotionFieldValues,
    *,
    key_prefix: str,
) -> NotionFieldValues:
    edited: NotionFieldValues = {}
    for field_name in _ordered_recipe_field_names(schema):
        if field_name not in fields and field_name not in schema.all_columns:
            continue
        value = fields.get(field_name)
        column = schema.all_columns.get(field_name)
        widget_key = f"{key_prefix}_{field_name}"

        if column and column.type in ("select", "status"):
            options = ["", *column.options]
            current = value if value in column.options else ""
            edited[field_name] = st.selectbox(
                field_name,
                options,
                index=options.index(current) if current else 0,
                key=widget_key,
            )
        elif column and column.type == "multi_select":
            edited[field_name] = st.multiselect(
                field_name,
                column.options,
                default=value if isinstance(value, list) else [],
                key=widget_key,
            )
        elif column and column.type == "checkbox":
            edited[field_name] = st.checkbox(
                field_name,
                value=bool(value),
                key=widget_key,
            )
        elif field_name == schema.ingredients_column:
            edited[field_name] = st.text_area(
                field_name,
                value=value or "",
                height=180,
                placeholder="One ingredient per line\neggs\n2 cups flour\n1 lb chicken",
                help="Paste or edit ingredients here. One line per ingredient.",
                key=widget_key,
            )
        elif field_name == schema.name_column:
            edited[field_name] = st.text_input(
                field_name,
                value=str(value or ""),
                placeholder="Recipe name",
                key=widget_key,
            )
        elif field_name == schema.link_column:
            edited[field_name] = st.text_input(
                field_name,
                value=str(value or ""),
                placeholder="https://... (optional for manual recipes)",
                key=widget_key,
            )
        else:
            edited[field_name] = st.text_input(
                field_name,
                value=str(value or ""),
                key=widget_key,
            )
    return edited


def _preview_recipes(db: NotionRecipesDB, urls: list[str]) -> list[dict]:
    schema = db.schema
    previews: list[dict] = []

    for url in urls:
        existing = db.find_by_link(url)
        if existing:
            previews.append({"status": "duplicate", "name": existing.name, "url": url})
            continue

        try:
            scraped = scrape_recipe(url)
        except ScrapeError as exc:
            previews.append(
                {
                    "status": "manual",
                    "url": url,
                    "error": str(exc),
                    "fields": _base_recipe_fields(
                        schema,
                        url=url,
                        name=_guess_recipe_name_from_url(url),
                    ),
                }
            )
            continue

        filter_columns = [(col.name, col.type, col.options) for col in schema.filter_columns]
        weeknight_column = (
            DEFAULT_WEEKNIGHT_COLUMN if DEFAULT_WEEKNIGHT_COLUMN in schema.all_columns else None
        )
        inferred = classify_recipe(
            scraped.title,
            scraped.ingredients,
            filter_columns,
            total_minutes=scraped.total_time_minutes,
            weeknight_column=weeknight_column,
        )
        ingredients_text = (
            ingredients_to_text(scraped.ingredients) if schema.ingredients_column else ""
        )
        fields = _base_recipe_fields(
            schema,
            url=url,
            name=scraped.title,
            ingredients=ingredients_text,
            inferred=inferred,
        )

        if schema.ingredients_column and not scraped.ingredients:
            previews.append(
                {
                    "status": "manual",
                    "url": url,
                    "error": "No ingredients found on this page. Paste them below.",
                    "fields": fields,
                }
            )
        else:
            previews.append({"status": "ready", "url": url, "fields": fields})

    return previews


