"""Streamlit UI for Grocery Wizard."""

from __future__ import annotations

import streamlit as st

from src.grocery_wizard.classify import classify_recipe
from src.grocery_wizard.config import load_config
from src.grocery_wizard.grocery_list import (
    WEEK_PLAN_PATH,
    _load_week_plan_names,
    build_grocery_list,
)
from src.grocery_wizard.ingredients_sync import (
    find_recipes_needing_sync,
    format_sync_summary,
    run_sync,
)
from src.grocery_wizard.notion import NotionRecipesDB
from src.grocery_wizard.scraper import ScrapeError, ingredients_to_text, scrape_recipe


@st.cache_resource
def get_db() -> NotionRecipesDB:
    config = load_config()
    return NotionRecipesDB(config)


def main() -> None:
    st.set_page_config(
        page_title="Grocery Wizard",
        page_icon="🛒",
        layout="centered",
    )
    st.title("Grocery Wizard")

    tab_add, tab_sync, tab_plan, tab_grocery = st.tabs(
        ["Add Recipe", "Sync Ingredients", "Plan Meals", "Grocery List"]
    )

    with tab_add:
        render_add_recipe()
    with tab_sync:
        render_sync()
    with tab_plan:
        render_plan_meals()
    with tab_grocery:
        render_grocery_list()


def render_add_recipe() -> None:
    st.subheader("Add Recipe")
    st.caption("Paste recipe URL(s). Ingredients are scraped once and saved to Notion.")

    db = get_db()
    schema = db.schema

    urls_text = st.text_area(
        "Recipe URL(s)",
        placeholder="https://example.com/recipe\n(one per line)",
        height=100,
    )

    if st.button("Scrape & preview", type="primary"):
        urls = [line.strip() for line in urls_text.splitlines() if line.strip()]
        if not urls:
            st.warning("Enter at least one URL.")
        else:
            st.session_state["preview_recipes"] = _preview_recipes(db, urls)

    previews = st.session_state.get("preview_recipes", [])
    for i, preview in enumerate(previews):
        if preview.get("status") == "duplicate":
            st.info(f"Already in Notion: {preview['name']} ({preview['url']})")
            continue
        if preview.get("status") == "error":
            st.error(f"Failed to scrape {preview['url']}: {preview['error']}")
            continue

        with st.expander(
            f"Review: {preview['fields'].get(schema.name_column, 'Recipe')}", expanded=True
        ):
            edited = {}
            for field_name, value in preview["fields"].items():
                column = schema.all_columns.get(field_name)
                if column and column.type in ("select", "status"):
                    options = [""] + column.options
                    current = value if value in column.options else ""
                    edited[field_name] = st.selectbox(
                        field_name,
                        options,
                        index=options.index(current) if current else 0,
                        key=f"sel_{i}_{field_name}",
                    )
                elif column and column.type == "multi_select":
                    edited[field_name] = st.multiselect(
                        field_name,
                        column.options,
                        default=value if isinstance(value, list) else [],
                        key=f"ms_{i}_{field_name}",
                    )
                elif column and column.type == "checkbox":
                    edited[field_name] = st.checkbox(
                        field_name,
                        value=bool(value),
                        key=f"cb_{i}_{field_name}",
                    )
                elif field_name == schema.ingredients_column:
                    edited[field_name] = st.text_area(
                        field_name,
                        value=value or "",
                        height=150,
                        key=f"ing_{i}",
                    )
                else:
                    edited[field_name] = st.text_input(
                        field_name, value=str(value or ""), key=f"txt_{i}_{field_name}"
                    )

            if st.button("Save to Notion", key=f"save_{i}"):
                cleaned = {k: v for k, v in edited.items() if v not in (None, "", [])}
                recipe = db.create_recipe(cleaned)
                st.success(f"Created: {recipe.name}")
                previews[i]["status"] = "saved"
                st.session_state["preview_recipes"] = previews


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
            filter_columns = [(col.name, col.type, col.options) for col in schema.filter_columns]
            inferred = classify_recipe(scraped.title, scraped.ingredients, filter_columns)

            fields: dict = {
                schema.name_column: scraped.title,
                schema.link_column: url,
            }
            if schema.ingredients_column:
                fields[schema.ingredients_column] = ingredients_to_text(scraped.ingredients)
            fields.update(inferred)
            for col in schema.checkbox_columns:
                fields.setdefault(col.name, False)

            previews.append({"status": "ready", "url": url, "fields": fields})
        except ScrapeError as exc:
            previews.append({"status": "error", "url": url, "error": str(exc)})

    return previews


def render_sync() -> None:
    st.subheader("Sync Ingredients")
    st.caption(
        "For recipes added directly in Notion (Link filled, Ingredients empty), "
        "scrape once and save to the Ingredients column."
    )

    db = get_db()
    dry_run = st.checkbox("Dry run (preview only)")
    force = st.checkbox("Force re-scrape (overwrite existing Ingredients)")

    needing = find_recipes_needing_sync(db, force=force)
    if needing:
        st.write(f"**{len(needing)} recipe(s) need syncing:**")
        for recipe in needing:
            st.write(f"- {recipe.name}")
    else:
        st.success("All recipes with links already have ingredients.")

    if st.button("Run sync", type="primary"):
        with st.spinner("Syncing..."):
            summary = run_sync(db, dry_run=dry_run, force=force)
        st.info(format_sync_summary(summary, dry_run=dry_run))
        if summary.synced:
            get_db.clear()


def render_plan_meals() -> None:
    st.subheader("Plan Meals")
    st.info("Coming soon — weekly meal planning will live here.")
    st.caption(
        "For now, use the Grocery List tab to pick recipes manually, "
        "or run `plan-recipes` from the CLI when meal planning is built."
    )


def render_grocery_list() -> None:
    st.subheader("Grocery List")
    st.caption("Reads Ingredients from Notion. Normalizes and excludes pantry staples.")

    db = get_db()
    all_recipes = db.query_recipes()
    recipe_names = [r.name for r in all_recipes]

    week_plan_names = _load_week_plan_names(WEEK_PLAN_PATH)
    use_week_plan = False
    if week_plan_names:
        use_week_plan = st.checkbox(
            f"Use week plan ({len(week_plan_names)} recipes)",
            value=True,
        )

    if use_week_plan and week_plan_names:
        selected = week_plan_names
        st.write("Recipes from week plan:", ", ".join(week_plan_names))
    else:
        selected = st.multiselect("Select recipes", recipe_names)

    sync_first = st.checkbox("Sync ingredients first (scrape missing)")
    exclude_pantry = st.checkbox("Exclude pantry items", value=True)

    if st.button("Generate list", type="primary"):
        if not selected:
            st.warning("Select at least one recipe.")
            return

        with st.spinner("Building grocery list..."):
            items, excluded = build_grocery_list(
                db,
                recipe_names=selected,
                backfill_missing=sync_first,
                exclude_pantry=exclude_pantry,
            )

        if not items and not excluded:
            st.warning("No grocery items found.")
            return

        if excluded:
            st.write("**Excluded staples (already in your pantry)**")
            for index, item in enumerate(excluded, start=1):
                st.write(f"{index}. {item}")
            readd = st.multiselect(
                "Add excluded staples back?",
                options=excluded,
                default=[],
            )
        else:
            readd = []

        draft_items = list(items)
        existing = {item.lower() for item in draft_items}
        for item in readd:
            if item.lower() not in existing:
                draft_items.append(item)
                existing.add(item.lower())
        draft_items.sort(key=str.lower)

        if draft_items:
            st.write("**Draft grocery list**")
            st.text("\n".join(draft_items))

        staples_text = st.text_area(
            "Additional items (one per line)",
            placeholder="milk\neggs\nbread",
            height=80,
            key="grocery_additional_items",
        )
        staples = [
            line.strip().lstrip("-•* ").strip()
            for line in staples_text.splitlines()
            if line.strip()
        ]

        final_items = list(draft_items)
        existing = {item.lower() for item in final_items}
        for item in staples:
            if item.lower() not in existing:
                final_items.append(item)
                existing.add(item.lower())
        final_items.sort(key=str.lower)

        if final_items:
            st.write("**Final grocery list**")
            list_text = "\n".join(final_items)
            st.text_area("Copy-ready list", value=list_text, height=300)
        elif not excluded:
            st.warning("No grocery items found.")


if __name__ == "__main__":
    main()
