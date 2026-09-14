"""Streamlit UI for Grocery Wizard."""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit executes this file as a script; add repo root so `src.*` imports work.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json
from datetime import UTC, date, datetime
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from src.grocery_wizard.config import RECURRING_WEEKLY_ITEMS_PATH, WEEK_PLAN_PATH, load_config
from src.grocery_wizard.dev.edit_log import log_ingredient_edits
from src.grocery_wizard.ingredients.sync import prepare_ingredients_for_notion
from src.grocery_wizard.integrations.notion import (
    ColumnInfo,
    DatabaseSchema,
    NotionFieldValues,
    NotionRecipesDB,
)
from src.grocery_wizard.planning.meal_planner import (
    MealPlanFilters,
    build_ingredient_index,
    default_filters,
    filter_recipes,
    replace_meals_in_plan,
    save_week_plan,
    suggest_meals,
)
from src.grocery_wizard.planning.saved_weekly_plans import (
    SavedWeeklyPlan,
    ensure_saved_weekly_plan,
    find_matching_plan,
    list_saved_plans,
    load_plan_recipes,
    normalize_recipe_names,
    week_start_sunday,
)
from src.grocery_wizard.recipes.classify import classify_recipe
from src.grocery_wizard.recipes.scraper import ScrapeError, ingredients_to_text, scrape_recipe
from src.grocery_wizard.recipes.weeknight import DEFAULT_WEEKNIGHT_COLUMN
from src.grocery_wizard.shopping.grocery_list import (
    build_grocery_list,
    format_item_provenance,
    format_meals_and_grocery_list,
    merge_grocery_items,
)
from src.grocery_wizard.shopping.line_items import parse_line_items
from src.grocery_wizard.shopping.pantry import append_pantry_item
from src.grocery_wizard.shopping.recurring_weekly_items import (
    apply_recurring_session_overrides,
    load_recurring_weekly_items,
    remove_recurring_weekly_item,
    write_recurring_weekly_items,
)


def _meal_entries_with_links(
    db: NotionRecipesDB,
    meal_names: list[str],
) -> list[tuple[str, str | None]]:
    recipes_by_name = {recipe.name.lower(): recipe for recipe in db.query_recipes()}
    entries: list[tuple[str, str | None]] = []
    for name in meal_names:
        recipe = recipes_by_name.get(name.lower())
        link = recipe.link if recipe else None
        entries.append((name, link))
    return entries


def _render_copy_button(text: str, *, label: str = "Copy list", key: str) -> None:
    """One-click copy for the final grocery list (falls back to manual copy on HTTP)."""
    components.html(
        f"""
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <button id="btn_{key}" style="
            background: #8b1a5c;
            border: 1px solid #5c1040;
            border-radius: 0.5rem;
            color: #ffffff;
            font-weight: 600;
            cursor: pointer;
            font-size: 1rem;
            padding: 0.45rem 1rem;
            width: 100%;
          ">{label}</button>
          <span id="status_{key}" style="
            color:#5c1040; font-size:0.9rem; white-space:nowrap;
          "></span>
        </div>
        <script>
          const text = {json.dumps(text)};
          document.getElementById("btn_{key}").onclick = async () => {{
            const status = document.getElementById("status_{key}");
            try {{
              await navigator.clipboard.writeText(text);
              status.textContent = "Copied!";
            }} catch (err) {{
              status.textContent = "Tap list below to copy";
            }}
            setTimeout(() => {{ status.textContent = ""; }}, 2000);
          }};
        </script>
        """,
        height=52,
    )


def _parse_line_items(text: str) -> list[str]:
    """Thin wrapper around the shared :func:`parse_line_items` helper."""
    return parse_line_items(text)


def _compute_grocery_drafts(
    items: list[str],
    readd: list[str],
    additional_text: str,
    *,
    run_removals: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    draft_items = merge_grocery_items(items, readd)
    final_items = merge_grocery_items(items, readd, _parse_line_items(additional_text))
    if run_removals:
        final_items = _apply_run_removals(final_items, run_removals)
    return draft_items, final_items


def _apply_run_removals(items: list[str], removals: set[str]) -> list[str]:
    """Drop lines whose normalized text matches a one-time removal for this run."""
    if not removals:
        return items
    keys = {name.strip().lower() for name in removals if name.strip()}
    filtered: list[str] = []
    for line in items:
        lowered = line.strip().lower()
        if any(key in lowered or lowered in key for key in keys):
            continue
        filtered.append(line)
    return filtered


def _grocery_line_matches_name(line: str, name: str) -> bool:
    lowered_line = line.strip().lower()
    lowered_name = name.strip().lower()
    if not lowered_line or not lowered_name:
        return False
    return lowered_name in lowered_line or lowered_line in lowered_name


def _save_recurring_template(text: str, *, path: Path = RECURRING_WEEKLY_ITEMS_PATH) -> None:
    """Persist the recurring weekly template (flow B — intentional default edits)."""
    write_recurring_weekly_items(path, _parse_line_items(text))


def _render_recurring_template_editor() -> None:
    """Dedicated entry point to view/edit the saved recurring template."""
    with st.expander("Recurring template (future weeks)", expanded=False):
        st.caption(
            "This is the default recurring list for every new week. Saving here does not "
            "affect the per-week list above unless you start a new run."
        )
        template = load_recurring_weekly_items()
        edited = st.text_area(
            "Default recurring items (one per line)",
            value="\n".join(template),
            height=120,
            key="recurring_template_editor",
        )
        if st.button("Save recurring template", type="primary", key="save_recurring_template"):
            _save_recurring_template(edited)
            st.success("Saved recurring template for future weeks.")
            st.rerun()


def _recipes_ingredient_cache_key(recipes: list) -> tuple[tuple[str, str], ...]:
    """Fingerprint recipe ingredient text so caches invalidate when content changes."""
    return tuple((recipe.page_id, recipe.ingredients or "") for recipe in recipes)


def _ingredient_options_from_index(ingredient_index: dict[str, set[str]]) -> list[str]:
    """Return sorted unique normalized ingredient names from a precomputed index."""
    return sorted({name for names in ingredient_index.values() for name in names})


def _render_meal_plan_filters(
    filter_columns: list[ColumnInfo],
    defaults: MealPlanFilters,
    *,
    key_prefix: str,
    ingredient_index: dict[str, set[str]] | None = None,
) -> MealPlanFilters:
    values: dict[str, Any] = {}
    for column in filter_columns:
        default_val = defaults.values.get(column.name)
        if column.type in ("select", "status"):
            options = ["Any", *column.options]
            current = default_val if default_val in column.options else "Any"
            picked = st.selectbox(
                column.name,
                options,
                index=options.index(current),
                key=f"{key_prefix}_{column.name}",
            )
            if picked != "Any":
                values[column.name] = picked
        elif column.type == "multi_select":
            default_list = default_val if isinstance(default_val, list) else []
            picked = st.multiselect(
                column.name,
                column.options,
                default=default_list,
                key=f"{key_prefix}_{column.name}",
            )
            if picked:
                values[column.name] = picked
        elif column.type == "checkbox":
            checked = st.checkbox(
                column.name,
                value=bool(default_val) if isinstance(default_val, bool) else False,
                key=f"{key_prefix}_{column.name}",
            )
            if isinstance(default_val, bool):
                values[column.name] = checked
            elif checked:
                values[column.name] = True

    ingredient_names: list[str] = []
    ingredient_mode = "include"

    if ingredient_index is not None:
        ingredient_options = _ingredient_options_from_index(ingredient_index)

        st.markdown("**Ingredients**")
        if ingredient_options:
            st.caption(f"{len(ingredient_options)} ingredients from your recipes")
        ingredient_names = st.multiselect(
            "Pick one or more ingredients",
            ingredient_options,
            default=[],
            key=f"{key_prefix}_ingredient_names",
            label_visibility="collapsed",
        )
        if ingredient_names:
            ingredient_mode = st.radio(
                "Filter mode",
                options=["include", "exclude"],
                format_func=lambda m: (
                    "Include recipes with any selected ingredient"
                    if m == "include"
                    else "Exclude recipes with any selected ingredient"
                ),
                index=0,
                key=f"{key_prefix}_ingredient_mode",
                label_visibility="collapsed",
            )

    return MealPlanFilters(
        values=values,
        ingredient_names=list(ingredient_names),
        ingredient_mode=ingredient_mode,
    )


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
    _inject_app_styles()
    st.title("Grocery Wizard")

    tab_add, tab_weekly = st.tabs(["Add Recipe", "Create weekly plan"])

    with tab_add:
        render_add_recipe()
    with tab_weekly:
        render_create_weekly_plan()


def _inject_app_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --gw-bg: #ffe4f0;
            --gw-text: #5c1040;
            --gw-text-muted: #7a2858;
            --gw-input-bg: #fff9fc;
            --gw-accent: #8b1a5c;
            --gw-blue: #b8d9f0;
            --gw-blue-strong: #6baee0;
            --gw-blue-text: #1a4a6e;
        }

        .stApp {
            background-color: var(--gw-bg);
            color: var(--gw-text);
        }

        .stApp h1, .stApp h2, .stApp h3, .stApp h4,
        .stApp label, .stApp p, .stApp li,
        .stApp [data-testid="stMarkdownContainer"] {
            color: var(--gw-text);
        }

        .stApp .stCaption, .stApp small {
            color: var(--gw-text-muted);
        }

        .stTextInput input,
        .stTextArea textarea,
        .stNumberInput input,
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div {
            background-color: var(--gw-input-bg) !important;
            color: var(--gw-text) !important;
            border-color: #d48aad !important;
        }

        [data-testid="stText"] pre,
        [data-testid="stText"] code {
            background-color: var(--gw-input-bg) !important;
            color: var(--gw-text) !important;
        }

        .stTextArea textarea:disabled {
            color: var(--gw-text) !important;
            -webkit-text-fill-color: var(--gw-text) !important;
            opacity: 1 !important;
        }

        [data-baseweb="tab"] {
            color: var(--gw-text-muted) !important;
        }

        [data-baseweb="tab"][aria-selected="true"] {
            color: var(--gw-text) !important;
            border-bottom-color: var(--gw-accent) !important;
        }

        .stButton button[kind="primary"],
        .stButton button[data-testid="baseButton-primary"],
        .stDownloadButton button {
            background-color: var(--gw-accent) !important;
            border-color: var(--gw-accent) !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        .stButton button[kind="primary"] p,
        .stButton button[kind="primary"] span,
        .stButton button[kind="primary"] div,
        .stButton button[data-testid="baseButton-primary"] p,
        .stButton button[data-testid="baseButton-primary"] span,
        .stButton button[data-testid="baseButton-primary"] div,
        .stDownloadButton button p,
        .stDownloadButton button span,
        .stDownloadButton button div {
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        .stButton button[kind="secondary"],
        .stButton button[data-testid="baseButton-secondary"] {
            background-color: var(--gw-input-bg) !important;
            border-color: #d48aad !important;
            color: var(--gw-text) !important;
        }

        .stButton button[kind="secondary"] p,
        .stButton button[kind="secondary"] span,
        .stButton button[data-testid="baseButton-secondary"] p,
        .stButton button[data-testid="baseButton-secondary"] span {
            color: var(--gw-text) !important;
        }

        [data-testid="stExpander"] summary {
            color: var(--gw-text) !important;
        }

        /* Checkboxes */
        .stCheckbox label[data-baseweb="checkbox"] > span[data-checked="true"],
        label[data-baseweb="checkbox"] > span[aria-checked="true"] {
            background-color: var(--gw-blue-strong) !important;
            border-color: var(--gw-blue-strong) !important;
        }

        .stCheckbox label[data-baseweb="checkbox"] > span[data-checked="false"],
        label[data-baseweb="checkbox"] > span[aria-checked="false"] {
            border-color: var(--gw-blue-strong) !important;
        }

        /* Radio buttons */
        .stRadio label[data-baseweb="radio"] > div:first-child {
            border-color: var(--gw-blue-strong) !important;
        }

        .stRadio label[data-baseweb="radio"] > div:first-child[aria-checked="true"],
        label[data-baseweb="radio"] div[data-checked="true"] {
            background-color: var(--gw-blue-strong) !important;
            border-color: var(--gw-blue-strong) !important;
        }

        /* Multiselect tags / bubbles */
        [data-baseweb="tag"] {
            background-color: var(--gw-blue) !important;
            color: var(--gw-blue-text) !important;
            border-color: var(--gw-blue-strong) !important;
        }

        [data-baseweb="tag"] svg {
            fill: var(--gw-blue-text) !important;
        }

        /* Dropdown selected rows */
        li[role="option"][aria-selected="true"] {
            background-color: var(--gw-blue) !important;
            color: var(--gw-blue-text) !important;
        }

        [data-testid="stToolbar"], footer, #MainMenu {
            visibility: hidden;
        }
        [data-testid="stToolbar"] {
            height: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def _current_plan_names() -> list[str]:
    return _parse_line_items(st.session_state.get("plan_meals_text", "").replace(",", "\n"))


def _session_pantry_extra() -> set[str]:
    if "grocery_session_pantry" not in st.session_state:
        st.session_state.grocery_session_pantry = set()
    return st.session_state.grocery_session_pantry


def _session_recurring_removals() -> set[str]:
    if "grocery_session_recurring_removals" not in st.session_state:
        st.session_state.grocery_session_recurring_removals = set()
    return st.session_state.grocery_session_recurring_removals


def _session_recurring_additions() -> list[str]:
    if "grocery_session_recurring_additions" not in st.session_state:
        st.session_state.grocery_session_recurring_additions = []
    return st.session_state.grocery_session_recurring_additions


def _clear_grocery_session_overrides() -> None:
    st.session_state.pop("grocery_session_pantry", None)
    st.session_state.pop("grocery_session_recurring_removals", None)
    st.session_state.pop("grocery_session_recurring_additions", None)


def _effective_recurring_items(template: list[str]) -> list[str]:
    return apply_recurring_session_overrides(
        template,
        additions=_session_recurring_additions(),
        removals=_session_recurring_removals(),
    )


def _render_persistence_scope_radio(*, key: str) -> str:
    """Return ``session`` or ``template`` for pantry / recurring edits."""
    return st.radio(
        "Apply change to",
        options=["session", "template"],
        format_func=lambda choice: (
            "This run only (this week's grocery list)"
            if choice == "session"
            else "Recurring template (saved for future weeks)"
        ),
        horizontal=False,
        key=key,
    )


def _render_pantry_and_weekly_item_manager(template_recurring: list[str]) -> None:
    """Add pantry staples or adjust the weekly recurring list with an explicit scope."""
    st.markdown("**Pantry & weekly recurring list**")
    st.caption(
        "Add pantry items or remove recurring weekly items. Choose whether the change "
        "applies only to this run or updates the saved template."
    )
    scope = _render_persistence_scope_radio(key="pantry_weekly_scope")

    add_pantry = st.text_input(
        "Add pantry item",
        placeholder="e.g. soy sauce",
        key="manage_add_pantry_item",
    )
    if st.button("Add to pantry", key="manage_add_pantry_btn"):
        name = add_pantry.strip()
        if not name:
            st.warning("Enter an item name.")
        elif scope == "session":
            _session_pantry_extra().add(name.lower())
            st.success(f"Added “{name}” to pantry for this run only.")
            st.rerun()
        elif append_pantry_item(name):
            st.success(f"Saved “{name}” to the pantry template.")
            st.rerun()
        else:
            st.warning("Could not add — empty name or already in pantry.")

    remove_weekly = st.text_input(
        "Remove from weekly recurring list",
        placeholder="Item name to remove",
        key="manage_remove_weekly_item",
    )
    if st.button("Remove weekly item", key="manage_remove_weekly_btn"):
        name = remove_weekly.strip()
        if not name:
            st.warning("Enter an item name to remove.")
        elif scope == "session":
            _session_recurring_removals().add(name.lower())
            st.success(f"Removed “{name}” from recurring items for this run only.")
            st.rerun()
        elif remove_recurring_weekly_item(name):
            st.success(f"Removed “{name}” from the recurring template.")
            st.rerun()
        else:
            st.warning("No matching item in the recurring template.")

    if scope == "session" and (
        _session_pantry_extra() or _session_recurring_removals() or _session_recurring_additions()
    ):
        st.caption(
            "This-run overrides: "
            f"pantry +{len(_session_pantry_extra())}, "
            f"recurring -{len(_session_recurring_removals())}, "
            f"+{len(_session_recurring_additions())} added."
        )

    _ = template_recurring  # reserved for display in later steps


def _clear_grocery_result() -> None:
    """Remove the cached grocery result, review state, and associated widget state."""
    for key in (
        "grocery_result",
        "grocery_additional_items",
        "grocery_readd",
        "grocery_final_list",
        "grocery_final_list_fingerprint",
        "meals_final_list",
        "meals_final_list_fingerprint",
        "grocery_per_recipe_review",
        "grocery_review_options",
    ):
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if key.startswith("review_ing_"):
            st.session_state.pop(key, None)


_WEEKLY_PLAN_MODES = ("new", "saved", "dev")


def _reset_weekly_plan_workflow(*, clear_mode: bool = False) -> None:
    """Clear meal-plan and grocery state for a fresh weekly-plan session."""
    for key in (
        "plan_meals_text",
        "plan_rejected_names",
        "plan_locked_recipes",
        "weekly_plan_loaded_slug",
        "weekly_plan_last_saved_slug",
        "weekly_plan_saved_fingerprint",
    ):
        st.session_state.pop(key, None)
    if clear_mode:
        st.session_state.pop("weekly_plan_mode", None)
    _clear_grocery_result()


def _weekly_plan_mode() -> str | None:
    mode = st.session_state.get("weekly_plan_mode")
    return mode if mode in _WEEKLY_PLAN_MODES else None


def _weekly_plan_reference_date() -> date:
    return datetime.now(tz=UTC).date()


def _weekly_plan_fingerprint(recipe_names: list[str]) -> tuple[str, ...]:
    week_start = week_start_sunday(_weekly_plan_reference_date())
    return (week_start.isoformat(), *normalize_recipe_names(recipe_names))


def _matching_saved_plan(recipe_names: list[str]) -> SavedWeeklyPlan | None:
    week_start = week_start_sunday(_weekly_plan_reference_date())
    recipes = normalize_recipe_names(recipe_names)
    if not recipes:
        return None
    return find_matching_plan(week_start, recipes)


def _invalidate_weekly_plan_save_state() -> None:
    st.session_state.pop("weekly_plan_last_saved_slug", None)
    st.session_state.pop("weekly_plan_saved_fingerprint", None)


def _sync_weekly_plan_save_state(recipe_names: list[str], plan: SavedWeeklyPlan) -> None:
    st.session_state.weekly_plan_last_saved_slug = plan.slug
    st.session_state.weekly_plan_saved_fingerprint = _weekly_plan_fingerprint(recipe_names)


def _commit_weekly_plan_to_repo(recipe_names: list[str]) -> SavedWeeklyPlan:
    """Ensure plan exists in repo CSV and refresh local week_plan.json for diversity hints."""
    plan, _created = ensure_saved_weekly_plan(recipe_names)
    save_week_plan(recipe_names, WEEK_PLAN_PATH)
    _sync_weekly_plan_save_state(recipe_names, plan)
    return plan


def _ensure_weekly_plan_saved_before_grocery(recipe_names: list[str]) -> None:
    """Auto-save meal plan when entering grocery flow if not already stored for this week."""
    if _weekly_plan_mode() == "dev" or not recipe_names:
        return
    plan, _created = ensure_saved_weekly_plan(recipe_names)
    save_week_plan(recipe_names, WEEK_PLAN_PATH)
    _sync_weekly_plan_save_state(recipe_names, plan)


def _render_save_plan_controls(recipe_names: list[str]) -> None:
    """Explicit save after meal generation (not used in dev mode)."""
    mode = _weekly_plan_mode()
    if mode == "dev" or not recipe_names:
        return

    existing = _matching_saved_plan(recipe_names)
    if existing is not None:
        st.success(f"Plan saved as **{existing.slug}**")
        return

    label = "Save plan to repo" if mode == "new" else "Save as new plan version"
    if st.button(label, type="secondary", key="save_weekly_plan"):
        _commit_weekly_plan_to_repo(recipe_names)
        st.rerun()


def _render_weekly_plan_entry() -> bool:
    """Prompt for new / saved / dev mode. Returns True when the user may continue planning."""
    mode = _weekly_plan_mode()
    if mode is not None:
        labels = {
            "new": "New weekly plan",
            "saved": "Continue from a saved plan",
            "dev": "Dev mode (do not save)",
        }
        loaded = st.session_state.get("weekly_plan_loaded_slug")
        detail = f" — loaded **{loaded}**" if mode == "saved" and loaded else ""
        st.info(f"**{labels[mode]}**{detail}")
        if st.button("Change how I started", key="weekly_plan_change_mode"):
            _reset_weekly_plan_workflow(clear_mode=True)
            st.rerun()
        return True

    st.markdown("### How do you want to start?")
    choice = st.radio(
        "Weekly plan session",
        options=_WEEKLY_PLAN_MODES,
        format_func=lambda value: {
            "new": (
                "Start a new list (Save plan anytime, or auto-saves when you create a grocery list)"
            ),
            "saved": (
                "Start from a saved list (grocery list is not saved; meals auto-save if new)"
            ),
            "dev": "Dev mode (nothing saved)",
        }[value],
        key="weekly_plan_mode_choice",
        label_visibility="collapsed",
    )

    saved_plans = list_saved_plans()
    selected_slug: str | None = None
    if choice == "saved":
        if not saved_plans:
            st.warning("No saved weekly plans yet. Start a new list first.")
        else:
            options = [plan.slug for plan in saved_plans]
            def _saved_plan_label(slug: str) -> str:
                for plan in saved_plans:
                    if plan.slug == slug:
                        return f"{plan.name} ({len(plan.recipes)} meals)"
                return slug

            selected_slug = st.selectbox(
                "Saved plan",
                options,
                format_func=_saved_plan_label,
                key="weekly_plan_saved_slug_pick",
            )

    if st.button("Continue", type="primary", key="weekly_plan_mode_continue"):
        if choice == "saved" and not saved_plans:
            return False
        st.session_state.weekly_plan_mode = choice
        _reset_weekly_plan_workflow(clear_mode=False)
        if choice == "saved" and selected_slug:
            st.session_state.plan_meals_text = "\n".join(load_plan_recipes(selected_slug))
            st.session_state.weekly_plan_loaded_slug = selected_slug
        elif choice in ("new", "dev"):
            st.session_state.plan_meals_text = ""
        st.rerun()

    return False


def _invalidate_stale_grocery_result() -> None:
    """Drop cached grocery results when the meal plan has changed."""
    result = st.session_state.get("grocery_result")
    if not result:
        return

    current_plan = tuple(_current_plan_names())
    cached_plan = result.get("week_plan")
    if cached_plan is not None and cached_plan != current_plan:
        _clear_grocery_result()



def _start_recipe_review(
    db: NotionRecipesDB,
    selected: list[str],
    *,
    exclude_pantry: bool,
    recurring_text: str,
    default_recurring: list[str],
    extra_items_text: str,
) -> None:
    """Fetch per-recipe ingredients from Notion and stash them for the review UI."""
    recipes_by_name = {r.name.lower(): r for r in db.query_recipes()}
    review: dict[str, str] = {}
    for name in selected:
        recipe = recipes_by_name.get(name.lower())
        review[name] = recipe.ingredients or "" if recipe else ""
    st.session_state.grocery_per_recipe_review = review
    st.session_state.grocery_review_options = {
        "exclude_pantry": exclude_pantry,
        "recurring_text": recurring_text,
        "default_recurring": default_recurring,
        "extra_items_text": extra_items_text,
    }


def _render_per_recipe_review(db: NotionRecipesDB, selected: list[str]) -> None:
    """Show one expandable text editor per recipe; build final list on confirmation."""
    review: dict[str, str] = st.session_state.grocery_per_recipe_review
    opts: dict = st.session_state.grocery_review_options

    st.markdown("### Review ingredients")
    st.caption(
        "Each recipe's ingredients are shown below. Edit or delete lines before building "
        "your grocery list."
    )

    for idx, name in enumerate(selected):
        original_text = review.get(name, "")
        widget_key = f"review_ing_{idx}"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = original_text
        with st.expander(name, expanded=False):
            st.text_area(
                "Ingredients (one per line)",
                height=160,
                key=widget_key,
                label_visibility="collapsed",
            )

    col_build, col_cancel = st.columns([3, 1])
    with col_build:
        if st.button("Build final list", type="primary", key="review_build_final"):
            overrides: dict[str, str] = {}
            edit_count = 0
            for idx, name in enumerate(selected):
                widget_key = f"review_ing_{idx}"
                edited_text = st.session_state.get(widget_key, review.get(name, ""))
                original_text = review.get(name, "")
                overrides[name.lower()] = edited_text
                edit_count += log_ingredient_edits(name, original_text, edited_text)

            recurring_weekly_items = _parse_line_items(opts["recurring_text"])

            with st.spinner("Building grocery list..."):
                items, excluded, _sync_summary, missing_ingredients, item_provenance, mismatches = (
                    build_grocery_list(
                        db,
                        recipe_names=selected,
                        exclude_pantry=opts["exclude_pantry"],
                        pantry_extra=_session_pantry_extra(),
                        recurring_weekly_items=recurring_weekly_items,
                        include_recurring_weekly_items=True,
                        ingredient_overrides=overrides,
                    )
                )

            extra_items_text = opts.get("extra_items_text", "")
            if not items and not excluded and not _parse_line_items(extra_items_text):
                if missing_ingredients:
                    st.warning(
                        "No grocery items found — all selected recipes are missing ingredients. "
                        f"Affected recipes: {', '.join(missing_ingredients)}."
                    )
                else:
                    st.warning("No grocery items found.")
                return

            st.session_state.grocery_result = {
                "items": items,
                "excluded": excluded,
                "missing_ingredients": missing_ingredients,
                "item_provenance": item_provenance,
                "name_link_mismatches": mismatches,
                "readd": [],
                "additional_text": extra_items_text,
                "recurring_items": list(recurring_weekly_items),
                "run_removals": [],
                "source_recipes": tuple(selected),
                "week_plan": tuple(selected),
                "edit_count": edit_count,
            }
            st.session_state.pop("grocery_per_recipe_review", None)
            st.session_state.pop("grocery_review_options", None)
            for key in list(st.session_state.keys()):
                if key.startswith("review_ing_"):
                    st.session_state.pop(key, None)
            st.rerun()
    with col_cancel:
        if st.button("Cancel", key="review_cancel"):
            _clear_grocery_result()
            st.rerun()


def render_create_weekly_plan() -> None:
    st.subheader("Create weekly plan")
    st.caption("Pick your meals, then get a grocery list.")

    _invalidate_stale_grocery_result()

    if not _render_weekly_plan_entry():
        return

    db = get_db()
    schema = db.schema
    config = load_config()
    all_recipes = db.query_recipes()
    recipe_names = [recipe.name for recipe in all_recipes]

    if "plan_meals_text" not in st.session_state:
        st.session_state.plan_meals_text = ""

    st.markdown("### 1. Meals")
    meal_count = st.number_input(
        "How many meals this week?",
        min_value=1,
        max_value=21,
        value=config.default_meals,
        step=1,
    )

    filter_defaults = default_filters(schema.all_columns)
    filter_columns = [*schema.filter_columns, *schema.checkbox_columns]

    # Cache ingredient index per loaded recipe set to avoid re-parsing on every widget interaction.
    recipes_cache_key = _recipes_ingredient_cache_key(all_recipes)
    if st.session_state.get("_ingredient_index_key") != recipes_cache_key:
        st.session_state["_ingredient_index_key"] = recipes_cache_key
        st.session_state["_ingredient_index"] = build_ingredient_index(all_recipes)
    ingredient_index: dict[str, set[str]] = st.session_state["_ingredient_index"]

    locked: list[str] = []
    with st.expander("More options", expanded=False):
        locked = st.multiselect(
            "Keep these recipes",
            recipe_names,
            default=[],
            key="plan_locked_recipes",
        )
        filters = _render_meal_plan_filters(
            filter_columns,
            filter_defaults,
            key_prefix="plan_filter",
            ingredient_index=ingredient_index,
        )

    suggestion_pool = filter_recipes(
        all_recipes, filters, schema.all_columns, ingredient_index=ingredient_index
    )

    if st.button("Build my plan", type="primary", key="build_plan"):
        plan = suggest_meals(
            all_recipes,
            meals=int(meal_count),
            locked_names=locked,
            filters=filters,
            schema_columns=schema.all_columns,
            ingredient_index=ingredient_index,
        )
        st.session_state.plan_meals_text = "\n".join(plan)
        st.session_state.plan_rejected_names = []
        _invalidate_weekly_plan_save_state()
        _clear_grocery_session_overrides()
        _clear_grocery_result()
        st.rerun()

    current_plan = _current_plan_names()
    if current_plan:

        def _apply_plan_swap(names_to_replace: list[str]) -> None:
            rejected = set(st.session_state.get("plan_rejected_names", []))
            new_plan, rejected = replace_meals_in_plan(
                current_plan,
                names_to_replace,
                all_recipes=all_recipes,
                pool=suggestion_pool,
                rejected_names=rejected,
            )
            st.session_state.plan_meals_text = "\n".join(new_plan)
            st.session_state.plan_rejected_names = sorted(rejected)
            _invalidate_weekly_plan_save_state()
            _clear_grocery_session_overrides()
            _clear_grocery_result()
            st.rerun()

        for index, name in enumerate(current_plan, start=1):
            meal_col, swap_col = st.columns([8, 1])
            with meal_col:
                st.write(f"{index}. {name}")
            with swap_col:
                if st.button("↺", key=f"swap_meal_{index}", help="Swap this meal"):
                    _apply_plan_swap([name])

        if st.button("↺ Re-generate everything", key="regenerate_plan"):
            rejected = set(st.session_state.get("plan_rejected_names", []))
            plan = suggest_meals(
                all_recipes,
                meals=int(meal_count),
                locked_names=locked,
                filters=filters,
                schema_columns=schema.all_columns,
                rejected_names=rejected,
                ingredient_index=ingredient_index,
            )
            st.session_state.plan_meals_text = "\n".join(plan)
            _invalidate_weekly_plan_save_state()
            _clear_grocery_session_overrides()
            _clear_grocery_result()
            st.rerun()

        with st.expander("Edit manually", expanded=False):
            st.text_area(
                "One recipe per line",
                height=160,
                key="plan_meals_text",
            )

        _render_save_plan_controls(_current_plan_names())

    st.divider()
    st.markdown("### 2. Grocery list")

    if st.session_state.get("grocery_result"):
        _render_grocery_result()
        return

    if st.session_state.get("grocery_per_recipe_review") is not None:
        _render_per_recipe_review(db, current_plan)
        return

    if not current_plan:
        st.caption("Build a meal plan above to continue.")
        return

    template_recurring = load_recurring_weekly_items()
    default_recurring = _effective_recurring_items(template_recurring)
    exclude_pantry = True
    recurring_text = "\n".join(default_recurring)

    with st.expander("Grocery list options", expanded=False):
        exclude_pantry = st.checkbox("Exclude pantry items", value=True)
        _render_pantry_and_weekly_item_manager(template_recurring)
        _render_recurring_template_editor()
        recurring_text = st.text_area(
            "Recurring items for this week (one per line)",
            value="\n".join(default_recurring),
            height=100,
            help=(
                "Edits here apply to this run only; use Recurring template scope above "
                "to change defaults."
            ),
        )

    extra_items_text = st.text_area(
        "Extra items (one per line)",
        value="",
        placeholder="milk\neggs\n- [ ] Flowers",
        height=80,
        key="grocery_pre_extra_items",
    )

    if st.button("Create grocery list", type="primary", key="create_grocery"):
        _ensure_weekly_plan_saved_before_grocery(current_plan)
        _clear_grocery_result()
        _start_recipe_review(
            db,
            current_plan,
            exclude_pantry=exclude_pantry,
            recurring_text=recurring_text,
            default_recurring=default_recurring,
            extra_items_text=extra_items_text,
        )
        st.rerun()


def _render_added_and_removed_summary(result: dict) -> None:
    recurring_items: list[str] = result.get("recurring_items") or []
    extra_items = _parse_line_items(result.get("additional_text", ""))
    added_items: list[str] = []
    seen: set[str] = set()
    for item in [*recurring_items, *extra_items]:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        added_items.append(item)

    excluded: list[str] = list(result.get("excluded") or [])

    st.markdown("### Added & removed this week")
    col_added, col_removed = st.columns(2)
    with col_added:
        st.markdown("**Added items**")
        st.caption("Recurring weekly items plus extras you entered.")
        if added_items:
            for item in added_items:
                st.write(f"- {item}")
        else:
            st.write("_None_")
    with col_removed:
        st.markdown("**Removed items (pantry)**")
        st.caption("Ingredients assumed on hand and left off the buy list.")
        if excluded:
            for item in excluded:
                st.write(f"- {item}")
        else:
            st.write("_None_")

    st.markdown("**Adjust before export**")
    pantry_name = st.text_input(
        "Add item to pantry",
        placeholder="Item to treat as pantry staple",
        key="output_add_pantry_name",
    )
    pantry_scope = _render_persistence_scope_radio(key="output_pantry_scope")
    if st.button("Add to pantry", key="output_add_pantry_btn"):
        name = pantry_name.strip()
        if not name:
            st.warning("Enter an item name.")
        else:
            if pantry_scope == "template":
                append_pantry_item(name)
            _session_pantry_extra().add(name.lower())
            items: list[str] = list(result["items"])
            result["items"] = [line for line in items if not _grocery_line_matches_name(line, name)]
            excluded_set = {e.lower() for e in result.get("excluded", [])}
            if name.lower() not in excluded_set:
                result["excluded"] = sorted([*result.get("excluded", []), name], key=str.lower)
            st.success(f"Moved “{name}” to pantry for this list.")
            st.rerun()

    remove_once = st.text_input(
        "Remove from this list once",
        placeholder="Item to skip on this run only",
        key="output_remove_once_name",
    )
    if st.button("Remove for this run", key="output_remove_once_btn"):
        name = remove_once.strip()
        if not name:
            st.warning("Enter an item name.")
        else:
            removals = set(result.get("run_removals") or [])
            removals.add(name.lower())
            result["run_removals"] = sorted(removals)
            st.success(f"Removed “{name}” from this run only.")
            st.rerun()


def _render_grocery_result() -> None:
    result = st.session_state.grocery_result
    items: list[str] = result["items"]
    excluded: list[str] = result["excluded"]
    missing_ingredients: list[str] = result.get("missing_ingredients", [])
    name_link_mismatches = result.get("name_link_mismatches", [])
    item_provenance: dict[str, list[str]] = result.get("item_provenance", {})
    meal_names = list(result.get("week_plan") or result.get("source_recipes") or [])

    if name_link_mismatches:
        for mismatch in name_link_mismatches:
            st.warning(
                f"Name/link mismatch for **{mismatch.recipe_name}**: "
                f"Link points to **{mismatch.link_title}**. "
                "Ingredients may be stale — verify Notion Name, Link, and Ingredients match."
            )

    if missing_ingredients:
        st.warning(
            f"Skipped {len(missing_ingredients)} recipe(s) with no ingredients in Notion: "
            f"{', '.join(missing_ingredients)}. "
            "Run `dev backfill-ingredients` to populate them from their links."
        )

    if item_provenance:
        with st.expander("Item sources (which recipe each item came from)"):
            st.text(format_item_provenance(item_provenance))

    _render_added_and_removed_summary(result)
    items = result["items"]
    excluded = result["excluded"]

    readd: list[str] = []
    additional_text = result.get("additional_text", "")

    with st.expander("Customize list", expanded=bool(excluded)):
        if excluded:
            st.caption("These pantry staples were left off your list.")
            readd = st.multiselect(
                "Add any back",
                options=excluded,
                default=result.get("readd", []),
                key="grocery_readd",
            )
        additional_text = st.text_area(
            "Extra items (one per line)",
            value=result.get("additional_text", ""),
            placeholder="milk\neggs",
            height=80,
            key="grocery_additional_items",
        )

    result["readd"] = readd
    result["additional_text"] = additional_text

    run_removals = set(result.get("run_removals") or [])
    _, final_items = _compute_grocery_drafts(
        items,
        readd,
        additional_text,
        run_removals=run_removals,
    )

    if final_items or meal_names:
        db = get_db()
        meals = _meal_entries_with_links(db, meal_names)
        list_text = format_meals_and_grocery_list(meals, final_items)

        if "\n\nGrocery List\n" in list_text:
            meals_copy_text, grocery_body = list_text.split("\n\nGrocery List\n", 1)
            grocery_copy_text = f"Grocery List\n{grocery_body}"
        else:
            meals_copy_text = list_text
            grocery_copy_text = "Grocery List"

        st.markdown("**Meals**")
        meals_fingerprint = tuple(meals)
        if st.session_state.get("meals_final_list_fingerprint") != meals_fingerprint:
            st.session_state["meals_final_list_fingerprint"] = meals_fingerprint
            st.session_state["meals_final_list"] = meals_copy_text
        st.text_area(
            "Meals",
            height=120,
            label_visibility="collapsed",
            key="meals_final_list",
        )
        meals_for_copy = st.session_state.get("meals_final_list", meals_copy_text)
        _render_copy_button(meals_for_copy, label="Copy meals", key="meals_copy")

        st.markdown("**Grocery List**")
        st.caption("Edit the list below before copying or downloading.")
        grocery_fingerprint = (tuple(final_items),)
        if st.session_state.get("grocery_final_list_fingerprint") != grocery_fingerprint:
            st.session_state["grocery_final_list_fingerprint"] = grocery_fingerprint
            st.session_state["grocery_final_list"] = grocery_copy_text
        st.text_area(
            "Grocery list",
            height=320,
            label_visibility="collapsed",
            key="grocery_final_list",
            help="Edit this consolidated list directly before copy or download.",
        )
        grocery_for_copy = st.session_state.get("grocery_final_list", grocery_copy_text)
        download_text = f"{meals_for_copy}\n\n{grocery_for_copy}"
        col_copy, col_download = st.columns(2)
        with col_copy:
            _render_copy_button(grocery_for_copy, label="Copy list", key="grocery_copy")
        with col_download:
            st.download_button(
                "Download",
                data=download_text,
                file_name="weekly_plan.txt",
                mime="text/plain",
                use_container_width=True,
            )
    elif not excluded and not meal_names:
        st.warning("No grocery items found.")

    edit_count: int = result.get("edit_count", 0)
    if edit_count:
        st.caption(f"_{edit_count} ingredient edit(s) logged for later review._")

    if st.button("Edit meals", key="grocery_edit_meals"):
        _clear_grocery_session_overrides()
        _clear_grocery_result()
        st.rerun()

    if st.button("Update list", key="grocery_update_list"):
        # Force recompute of both text areas by clearing fingerprints, then rerun.
        st.session_state.pop("grocery_final_list_fingerprint", None)
        st.session_state.pop("meals_final_list_fingerprint", None)
        st.rerun()


if __name__ == "__main__":
    main()
