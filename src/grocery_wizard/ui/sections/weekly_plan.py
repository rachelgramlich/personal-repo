"""Weekly meal plan and grocery list flow."""

from __future__ import annotations

from datetime import UTC, date, datetime

import streamlit as st

from src.grocery_wizard.config import WEEK_PLAN_PATH, load_config
from src.grocery_wizard.dev.edit_log import log_ingredient_edits
from src.grocery_wizard.ingredients.sync import format_ingredients_for_review
from src.grocery_wizard.integrations.notion import ColumnInfo, NotionRecipesDB, Recipe
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
    load_plan_recipes,
    normalize_recipe_names,
    week_start_sunday,
)
from src.grocery_wizard.shopping.grocery_list import (
    align_item_provenance_with_items,
    build_grocery_list,
    format_grocery_items_copy_text,
    format_item_provenance,
    format_meals_copy_text,
)
from src.grocery_wizard.shopping.recurring_weekly_items import (
    apply_recurring_session_overrides,
    load_recurring_weekly_items,
)
from src.grocery_wizard.ui.db_access import get_db
from src.grocery_wizard.ui.dev_jumps import (
    DEFAULT_DEV_MEAL_COUNT,
    DEV_JUMP_CAPTIONS,
    DEV_JUMP_FLOW_ORDER,
    DevJumpTarget,
    commit_dev_jump,
    dev_jump_display_title,
    pick_default_recipe_names,
)
from src.grocery_wizard.ui.grocery_helpers import (
    compute_grocery_drafts,
    meal_entries_with_links,
    parse_line_items_text,
    render_copy_download,
)
from src.grocery_wizard.ui.meal_plan_filters import (
    recipes_ingredient_cache_key,
    render_meal_plan_filters,
    week_level_plan_filter_columns,
)
from src.grocery_wizard.ui.notion_cache import (
    cached_query_recipes,
    cached_saved_plans,
    invalidate_notion_cache,
)


def _current_plan_names() -> list[str]:
    return parse_line_items_text(st.session_state.get("plan_meals_text", "").replace(",", "\n"))


def _write_plan_names(names: list[str]) -> None:
    st.session_state.plan_meals_text = "\n".join(names)


def _locked_recipes_for_plan_build(*, meal_count: int) -> list[str]:
    """Pinned meals for auto-fill: pre-build picks plus saved-plan loaded meals (#105)."""
    locked: list[str] = []
    for name in st.session_state.get("plan_prebuild_pinned_recipes") or []:
        if name and name not in locked:
            locked.append(name)
    if _weekly_plan_mode() == "saved":
        for name in _current_plan_names():
            if name not in locked:
                locked.append(name)
    return locked[: int(meal_count)]


def _render_prebuild_recipe_picker(all_recipes: list, *, meal_count: int) -> None:
    """Searchable multiselect to pin recipes before **Build my plan**."""
    all_names = sorted({recipe.name for recipe in all_recipes}, key=str.lower)
    if not all_names:
        st.caption("No recipes in Notion yet — add recipes to pin meals before building.")
        return

    current = _current_plan_names()
    if "plan_prebuild_pinned_recipes" not in st.session_state and current:
        st.session_state.plan_prebuild_pinned_recipes = list(current)

    max_pins = max(1, int(meal_count))
    st.multiselect(
        "Pin recipes before building",
        options=all_names,
        max_selections=max_pins,
        key="plan_prebuild_pinned_recipes",
        placeholder="Search and pick recipes to keep when building…",
        help=(
            f"Optional — pin up to {max_pins} meals. Auto-fill keeps these and suggests "
            "the rest from your filters below."
        ),
    )


def _set_plan_slot_recipe(plan: list[str], slot_index: int, recipe_name: str) -> list[str]:
    updated = list(plan)
    while len(updated) < slot_index:
        updated.append("")
    updated[slot_index - 1] = recipe_name
    return updated


def _render_slot_manual_picker(
    *,
    slot_index: int,
    current_name: str,
    all_recipes: list,
    filter_columns: list[ColumnInfo],
    filter_defaults: MealPlanFilters,
    schema_columns: dict[str, ColumnInfo],
    ingredient_index: dict[str, set[str]],
) -> None:
    with st.expander("Choose recipe manually", expanded=False):
        st.caption("Filters apply to this meal slot only.")
        slot_filters = render_meal_plan_filters(
            filter_columns,
            filter_defaults,
            key_prefix=f"plan_slot_{slot_index}",
            ingredient_index=ingredient_index,
        )
        slot_pool = filter_recipes(
            all_recipes,
            slot_filters,
            schema_columns,
            ingredient_index=ingredient_index,
        )
        slot_names = [recipe.name for recipe in slot_pool]
        if not slot_names:
            st.warning("No recipes match these filters.")
            return
        default_index = slot_names.index(current_name) if current_name in slot_names else 0
        picked = st.selectbox(
            "Recipe",
            slot_names,
            index=default_index,
            key=f"plan_slot_pick_{slot_index}",
        )
        if st.button("Use this recipe", key=f"plan_slot_apply_{slot_index}"):
            updated = _set_plan_slot_recipe(_current_plan_names(), slot_index, picked)
            _write_plan_names(updated)
            _invalidate_weekly_plan_save_state()
            _clear_grocery_session_overrides()
            _clear_grocery_result()
            st.rerun()


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


def _grocery_pre_extra_items_widget_key() -> str:
    epoch = int(st.session_state.get("grocery_pre_extra_items_epoch", 0))
    return f"grocery_pre_extra_items_{epoch}"


def _bump_grocery_pre_extra_items_widget() -> None:
    """New widget key so Streamlit does not replay prior extra-item text."""
    st.session_state.grocery_pre_extra_items_epoch = (
        int(st.session_state.get("grocery_pre_extra_items_epoch", 0)) + 1
    )


def _clear_grocery_session_overrides() -> None:
    st.session_state.pop("grocery_session_pantry", None)
    st.session_state.pop("grocery_session_recurring_removals", None)
    st.session_state.pop("grocery_session_recurring_additions", None)
    _bump_grocery_pre_extra_items_widget()


def _clear_grocery_pre_extra_items() -> None:
    _bump_grocery_pre_extra_items_widget()


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


def _clear_grocery_result(*, clear_pre_extra_items: bool = True) -> None:
    """Remove the cached grocery result, review state, and associated widget state."""
    for key in (
        "grocery_result",
        "grocery_readd",
        "grocery_remove_once",
        "grocery_final_list",
        "grocery_final_list_fingerprint",
        "meals_final_list",
        "meals_final_list_fingerprint",
        "grocery_per_recipe_review",
        "grocery_review_options",
        "grocery_review_recipes",
    ):
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if key.startswith("review_ing_"):
            st.session_state.pop(key, None)
    if clear_pre_extra_items:
        _clear_grocery_pre_extra_items()


_WEEKLY_PLAN_MODES = ("new", "saved", "dev")


def _reset_weekly_plan_workflow(*, clear_mode: bool = False) -> None:
    """Clear meal-plan and grocery state for a fresh weekly-plan session."""
    for key in (
        "plan_meals_text",
        "plan_rejected_names",
        "weekly_plan_loaded_name",
        "weekly_plan_last_saved_name",
        "weekly_plan_saved_fingerprint",
        "plan_prebuild_pinned_recipes",
    ):
        st.session_state.pop(key, None)
    if clear_mode:
        st.session_state.pop("weekly_plan_mode", None)
        st.session_state.pop("plan_meal_count", None)
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
    return find_matching_plan(week_start, recipes, recipes_db=get_db())


def _invalidate_weekly_plan_save_state() -> None:
    st.session_state.pop("weekly_plan_last_saved_name", None)
    st.session_state.pop("weekly_plan_saved_fingerprint", None)


def _sync_weekly_plan_save_state(recipe_names: list[str], plan: SavedWeeklyPlan) -> None:
    st.session_state.weekly_plan_last_saved_name = plan.name
    st.session_state.weekly_plan_saved_fingerprint = _weekly_plan_fingerprint(recipe_names)


def _commit_weekly_plan_to_notion(recipe_names: list[str]) -> SavedWeeklyPlan:
    """Ensure plan exists in Notion and refresh local week_plan.json for diversity hints."""
    plan, created = ensure_saved_weekly_plan(recipe_names, recipes_db=get_db())
    save_week_plan(recipe_names, WEEK_PLAN_PATH)
    _sync_weekly_plan_save_state(recipe_names, plan)
    if created:
        invalidate_notion_cache()
    return plan


def _ensure_weekly_plan_saved_before_grocery(recipe_names: list[str]) -> None:
    """Auto-save meal plan when entering grocery flow if not already stored for this week."""
    if _weekly_plan_mode() == "dev" or not recipe_names:
        return
    plan, created = ensure_saved_weekly_plan(recipe_names, recipes_db=get_db())
    save_week_plan(recipe_names, WEEK_PLAN_PATH)
    _sync_weekly_plan_save_state(recipe_names, plan)
    if created:
        invalidate_notion_cache()


def _render_save_plan_controls(recipe_names: list[str]) -> None:
    """Explicit save after meal generation (not used in dev mode)."""
    mode = _weekly_plan_mode()
    if mode == "dev" or not recipe_names:
        return

    existing = _matching_saved_plan(recipe_names)
    if existing is not None:
        st.success(f"Plan saved as **{existing.name}**")
        return

    label = "Save plan to Notion" if mode == "new" else "Save as new plan version"
    if st.button(label, type="secondary", key="save_weekly_plan"):
        _commit_weekly_plan_to_notion(recipe_names)
        st.rerun()


def _render_dev_jump_tools(db: NotionRecipesDB) -> None:
    """Collapsed dev-only shortcuts to wizard steps for manual UAT."""
    if _weekly_plan_mode() != "dev":
        return

    with st.expander("Dev tools", expanded=False):
        st.caption(
            "Jump to a wizard step using a small default meal set from Notion "
            "(recipes with ingredients). Use when manually testing UI without "
            "clicking through meal generation each time."
        )
        def _dev_jump_bullet(target: DevJumpTarget) -> None:
            title = dev_jump_display_title(target)
            st.markdown(f"- **{title}** — {DEV_JUMP_CAPTIONS[target]}")

        def _dev_jump_button(
            target: DevJumpTarget,
            *,
            label: str,
            key_suffix: str,
            manual_recipes: list[str] | None,
        ) -> None:
            if not st.button(label, key=f"dev_jump_{target.value}_{key_suffix}"):
                return
            if manual_recipes is not None and not manual_recipes:
                st.warning("Pick at least one recipe for the manual meals jump.")
                return
            meal_count = int(
                st.session_state.get("plan_meal_count", DEFAULT_DEV_MEAL_COUNT)
            )
            if manual_recipes is not None:
                names = list(manual_recipes)
            else:
                names = pick_default_recipe_names(
                    db.query_recipes(),
                    meal_count=meal_count,
                )
            names = commit_dev_jump(st.session_state, db, target, names)
            if not names:
                st.error(
                    "No recipes in Notion to use for dev jump. Add recipes with "
                    "ingredients first."
                )
                return
            st.session_state.plan_prebuild_pinned_recipes = list(names)
            st.rerun()

        for step in DEV_JUMP_FLOW_ORDER:
            _dev_jump_bullet(step)

        all_names = sorted({recipe.name for recipe in db.query_recipes()}, key=str.lower)
        _dev_jump_button(
            DevJumpTarget.MEALS_FILLED,
            label="Meals filled: auto",
            key_suffix="auto",
            manual_recipes=None,
        )
        manual_pick = st.multiselect(
            "Choose recipes manually",
            options=all_names,
            key="dev_jump_manual_recipes",
            placeholder="Pick one or more recipes…",
        )
        _dev_jump_button(
            DevJumpTarget.MEALS_FILLED,
            label="Meals filled: manual",
            key_suffix="manual",
            manual_recipes=manual_pick,
        )
        _dev_jump_button(
            DevJumpTarget.PRE_BUILD_GROCERY,
            label="Pre-build grocery",
            key_suffix="btn_pre_build",
            manual_recipes=None,
        )
        _dev_jump_button(
            DevJumpTarget.PER_RECIPE_REVIEW,
            label="Per-recipe review",
            key_suffix="btn_review",
            manual_recipes=None,
        )
        _dev_jump_button(
            DevJumpTarget.GROCERY_RESULT,
            label="Final list",
            key_suffix="btn_final_list",
            manual_recipes=None,
        )


def _render_weekly_plan_entry() -> bool:
    """Prompt for new / saved / dev mode. Returns True when the user may continue planning."""
    mode = _weekly_plan_mode()
    if mode is not None:
        labels = {
            "new": "New weekly plan",
            "saved": "Continue from a saved plan",
            "dev": "Dev mode (do not save)",
        }
        loaded = st.session_state.get("weekly_plan_loaded_name")
        detail = f" — loaded **{loaded}**" if mode == "saved" and loaded else ""
        st.info(f"**{labels[mode]}**{detail}")
        if st.button("Change how I started", key="weekly_plan_change_mode"):
            _reset_weekly_plan_workflow(clear_mode=True)
            st.session_state.weekly_plan_mode_choice = "new"
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

    config = load_config()
    db = get_db()
    saved_plans = cached_saved_plans(
        db,
        weekly_plans_database_id=config.notion_weekly_meal_plans_database_id,
    )
    selected_plan_name: str | None = None
    if choice == "saved":
        if not saved_plans:
            st.warning("No saved weekly plans yet. Start a new list first.")
        else:
            options = [plan.name for plan in saved_plans]

            def _saved_plan_label(plan_name: str) -> str:
                for plan in saved_plans:
                    if plan.name == plan_name:
                        return f"{plan.name} ({len(plan.recipes)} meals)"
                return plan_name

            selected_plan_name = st.selectbox(
                "Saved plan",
                options,
                format_func=_saved_plan_label,
                key="weekly_plan_saved_name_pick",
            )

    if choice == "dev":
        st.session_state.weekly_plan_mode = "dev"
        _reset_weekly_plan_workflow(clear_mode=False)
        st.session_state.plan_meals_text = ""
        st.session_state.plan_meal_count = 1
        st.rerun()

    if st.button("Continue", type="primary", key="weekly_plan_mode_continue"):
        if choice == "saved" and not saved_plans:
            return False
        st.session_state.weekly_plan_mode = choice
        _reset_weekly_plan_workflow(clear_mode=False)
        if choice == "saved" and selected_plan_name:
            st.session_state.plan_meals_text = "\n".join(
                load_plan_recipes(selected_plan_name, recipes_db=get_db())
            )
            st.session_state.weekly_plan_loaded_name = selected_plan_name
        elif choice == "new":
            st.session_state.plan_meals_text = ""
            st.session_state.plan_meal_count = load_config().default_meals
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
    selected: list[str],
    recipes: list[Recipe],
    *,
    exclude_pantry: bool,
    recurring_text: str,
    default_recurring: list[str],
    extra_items_text: str,
) -> None:
    """Fetch per-recipe ingredients from Notion and stash them for the review UI."""
    recipes_by_name = {r.name.lower(): r for r in recipes}
    review: dict[str, str] = {}
    for name in selected:
        recipe = recipes_by_name.get(name.lower())
        raw = recipe.ingredients or "" if recipe else ""
        review[name] = format_ingredients_for_review(raw)
    st.session_state.grocery_per_recipe_review = review
    st.session_state.grocery_review_recipes = recipes
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

            recurring_weekly_items = parse_line_items_text(opts["recurring_text"])

            review_recipes = st.session_state.get("grocery_review_recipes")
            if review_recipes is None:
                review_recipes = cached_query_recipes(db)
            with st.spinner("Building grocery list..."):
                items, excluded, _sync_summary, missing_ingredients, item_provenance, mismatches = (
                    build_grocery_list(
                        db,
                        recipe_names=selected,
                        recipes=review_recipes,
                        exclude_pantry=opts["exclude_pantry"],
                        pantry_extra=_session_pantry_extra(),
                        recurring_weekly_items=recurring_weekly_items,
                        include_recurring_weekly_items=True,
                        ingredient_overrides=overrides,
                    )
                )

            extra_items_text = opts.get("extra_items_text", "")
            if not items and not excluded and not parse_line_items_text(extra_items_text):
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
            st.session_state.pop("grocery_review_recipes", None)
            for key in list(st.session_state.keys()):
                if key.startswith("review_ing_"):
                    st.session_state.pop(key, None)
            _clear_grocery_pre_extra_items()
            st.rerun()
    with col_cancel:
        if st.button("Cancel", key="review_cancel"):
            _clear_grocery_result(clear_pre_extra_items=False)
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
    all_recipes = cached_query_recipes(db)

    if "plan_meals_text" not in st.session_state:
        st.session_state.plan_meals_text = ""

    if _weekly_plan_mode() == "dev" and "plan_meal_count" not in st.session_state:
        st.session_state.plan_meal_count = 1

    st.markdown("### 1. Meals")
    if _weekly_plan_mode() == "dev":
        meal_count = st.number_input(
            "How many meals this week?",
            min_value=1,
            max_value=21,
            step=1,
            key="plan_meal_count",
        )
    else:
        meal_count = st.number_input(
            "How many meals this week?",
            min_value=1,
            max_value=21,
            value=int(st.session_state.get("plan_meal_count", config.default_meals)),
            step=1,
            key="plan_meal_count",
        )

    _render_dev_jump_tools(db)

    filter_defaults = default_filters(schema.all_columns)
    filter_columns = [*schema.filter_columns, *schema.checkbox_columns]

    # Cache ingredient index per loaded recipe set to avoid re-parsing on every widget interaction.
    recipes_cache_key = recipes_ingredient_cache_key(all_recipes)
    if st.session_state.get("_ingredient_index_key") != recipes_cache_key:
        st.session_state["_ingredient_index_key"] = recipes_cache_key
        st.session_state["_ingredient_index"] = build_ingredient_index(all_recipes)
    ingredient_index: dict[str, set[str]] = st.session_state["_ingredient_index"]

    st.markdown("#### Generate your plan")
    st.caption(
        "Pin specific recipes below, then auto-fill the rest using Meal and weeknight-friendly "
        "filters. Per-meal filters are still available after you build."
    )
    week_filter_columns = week_level_plan_filter_columns(schema)
    week_filters = render_meal_plan_filters(
        week_filter_columns,
        filter_defaults,
        key_prefix="plan_week_filter",
        ingredient_index=None,
    )

    suggestion_pool = filter_recipes(
        all_recipes, week_filters, schema.all_columns, ingredient_index=ingredient_index
    )

    _render_prebuild_recipe_picker(all_recipes, meal_count=int(meal_count))

    if st.button("Build my plan", type="primary", key="build_plan"):
        locked_for_build = _locked_recipes_for_plan_build(meal_count=int(meal_count))
        plan = suggest_meals(
            all_recipes,
            meals=int(meal_count),
            locked_names=locked_for_build,
            filters=week_filters,
            schema_columns=schema.all_columns,
            ingredient_index=ingredient_index,
        )
        _write_plan_names(plan)
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
            _write_plan_names(new_plan)
            st.session_state.plan_rejected_names = sorted(rejected)
            _invalidate_weekly_plan_save_state()
            _clear_grocery_session_overrides()
            _clear_grocery_result()
            st.rerun()

        st.markdown("**Your meals**")
        for index, name in enumerate(current_plan, start=1):
            meal_col, swap_col = st.columns([8, 1])
            with meal_col:
                st.write(f"**Meal {index}** — {name}")
                _render_slot_manual_picker(
                    slot_index=index,
                    current_name=name,
                    all_recipes=all_recipes,
                    filter_columns=filter_columns,
                    filter_defaults=filter_defaults,
                    schema_columns=schema.all_columns,
                    ingredient_index=ingredient_index,
                )
            with swap_col:
                if st.button("↺", key=f"swap_meal_{index}", help="Swap this meal"):
                    _apply_plan_swap([name])

        if len(current_plan) < int(meal_count) and st.button(
            "Fill remaining slots", key="fill_remaining_plan"
        ):
            plan = suggest_meals(
                all_recipes,
                meals=int(meal_count),
                locked_names=current_plan,
                filters=week_filters,
                schema_columns=schema.all_columns,
                ingredient_index=ingredient_index,
            )
            _write_plan_names(plan)
            _invalidate_weekly_plan_save_state()
            _clear_grocery_session_overrides()
            _clear_grocery_result()
            st.rerun()

        if st.button("↺ Re-generate everything", key="regenerate_plan"):
            rejected = set(st.session_state.get("plan_rejected_names", []))
            plan = suggest_meals(
                all_recipes,
                meals=int(meal_count),
                locked_names=[],
                filters=week_filters,
                schema_columns=schema.all_columns,
                rejected_names=rejected,
                ingredient_index=ingredient_index,
            )
            _write_plan_names(plan)
            _invalidate_weekly_plan_save_state()
            _clear_grocery_session_overrides()
            _clear_grocery_result()
            st.rerun()

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

    with st.expander("Pantry & Recurring Items", expanded=False):
        exclude_pantry = st.checkbox("Exclude pantry items", value=True)
        st.caption(
            "Edit saved pantry staples and recurring defaults in the **Pantry & recurring** tab."
        )
        recurring_text = st.text_area(
            "Recurring items for this week (one per line)",
            value="\n".join(default_recurring),
            height=100,
            help="Edits here apply to this run only; change saved defaults in Pantry & recurring.",
        )

    with st.expander("Add extra items", expanded=False):
        st.caption(
            "One-off items for this grocery run (not saved as recurring). "
            "Enter one item per line — checklist lines like `- [ ] Flowers` are OK."
        )
        extra_items_text = st.text_area(
            "Extra items (one per line)",
            placeholder="Start typing — one item per line",
            height=80,
            key=_grocery_pre_extra_items_widget_key(),
            label_visibility="collapsed",
        )

    if st.button("Create grocery list", type="primary", key="create_grocery"):
        _ensure_weekly_plan_saved_before_grocery(current_plan)
        _clear_grocery_result(clear_pre_extra_items=False)
        _start_recipe_review(
            current_plan,
            all_recipes,
            exclude_pantry=exclude_pantry,
            recurring_text=recurring_text,
            default_recurring=default_recurring,
            extra_items_text=extra_items_text,
        )
        st.rerun()


def _build_result_added_items(result: dict) -> list[str]:
    recurring_items: list[str] = result.get("recurring_items") or []
    extra_items = parse_line_items_text(result.get("additional_text", ""))
    added_items: list[str] = []
    seen: set[str] = set()
    for item in [*recurring_items, *extra_items]:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        added_items.append(item)
    return added_items


def _buy_list_line_options(result: dict) -> list[str]:
    """Lines on the buy list before one-time removals (for adjust multiselects)."""
    readd: list[str] = result.get("readd") or []
    _, lines = compute_grocery_drafts(
        result["items"],
        readd,
        result.get("additional_text", ""),
        run_removals=None,
    )
    return lines


def _run_removal_defaults(result: dict, buy_lines: list[str]) -> list[str]:
    removal_keys = {name.strip().lower() for name in (result.get("run_removals") or [])}
    if not removal_keys:
        return []
    defaults: list[str] = []
    for line in buy_lines:
        lowered = line.strip().lower()
        if any(key in lowered or lowered in key for key in removal_keys):
            defaults.append(line)
    return defaults


def _render_build_result_summary(result: dict) -> None:
    added_items = _build_result_added_items(result)
    excluded: list[str] = list(result.get("excluded") or [])

    st.markdown("### Summary (build result)")
    col_added, col_removed = st.columns(2)
    with col_added:
        st.markdown("**Added: recurring items and pasted extras**")
        if added_items:
            for item in added_items:
                st.write(f"- {item}")
        else:
            st.write("_None_")
    with col_removed:
        st.markdown("**Removed: items in the pantry**")
        if excluded:
            for item in excluded:
                st.write(f"- {item}")
        else:
            st.write("_None_")


def _render_adjust_this_week_list(result: dict) -> None:
    excluded: list[str] = list(result.get("excluded") or [])
    buy_lines = _buy_list_line_options(result)

    with st.expander("Adjust this week's list", expanded=False):
        if excluded:
            readd = st.multiselect(
                "Add to grocery list from pantry (1x)",
                options=excluded,
                default=result.get("readd", []),
                key="grocery_readd",
                help="Add pantry-removed items back for this trip only.",
            )
            result["readd"] = readd
        else:
            st.caption("No pantry-removed items to add back.")
            result["readd"] = []

        if buy_lines:
            remove_once = st.multiselect(
                "Remove from grocery list (1x)",
                options=buy_lines,
                default=_run_removal_defaults(result, buy_lines),
                key="grocery_remove_once",
                help="Skip these lines on this trip only; they are not added to the pantry.",
            )
            result["run_removals"] = sorted(
                {line.strip().lower() for line in remove_once if line.strip()}
            )
        else:
            st.caption("No buy-list lines to remove for this run.")


def _render_added_and_removed_summary(result: dict) -> None:
    """Post-build summary plus week-only list adjustments."""
    _render_build_result_summary(result)
    _render_adjust_this_week_list(result)


def _render_grocery_result() -> None:
    result = st.session_state.grocery_result
    items: list[str] = result["items"]
    excluded: list[str] = result["excluded"]
    missing_ingredients: list[str] = result.get("missing_ingredients", [])
    name_link_mismatches = result.get("name_link_mismatches", [])
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

    _render_added_and_removed_summary(result)
    items = result["items"]
    excluded = result["excluded"]

    readd: list[str] = list(result.get("readd") or [])
    additional_text = result.get("additional_text", "")

    run_removals = set(result.get("run_removals") or [])
    _, final_items = compute_grocery_drafts(
        items,
        readd,
        additional_text,
        run_removals=run_removals,
    )

    aligned_provenance = align_item_provenance_with_items(
        result.get("item_provenance", {}),
        final_items,
    )
    if aligned_provenance:
        with st.expander("Item sources (which recipe each item came from)"):
            st.text(format_item_provenance(aligned_provenance))

    if final_items or meal_names:
        db = get_db()
        meals = meal_entries_with_links(meal_names, cached_query_recipes(db))
        meals_copy_text = format_meals_copy_text(meals)
        grocery_copy_text = format_grocery_items_copy_text(final_items)

        st.markdown("### Customize list")
        st.caption("Edit meals and grocery copy before copying.")
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
        render_copy_download(
            meals_for_copy,
            label="Download meals",
            key="meals_copy",
            file_name="meals.txt",
        )

        st.markdown("**Grocery List**")
        st.caption("Edit the list below before copying.")
        grocery_fingerprint = (tuple(final_items),)
        if st.session_state.get("grocery_final_list_fingerprint") != grocery_fingerprint:
            st.session_state["grocery_final_list_fingerprint"] = grocery_fingerprint
            st.session_state["grocery_final_list"] = grocery_copy_text
        st.text_area(
            "Grocery list",
            height=320,
            label_visibility="collapsed",
            key="grocery_final_list",
            help="Edit this consolidated list directly before copy.",
        )
        grocery_for_copy = st.session_state.get("grocery_final_list", grocery_copy_text)
        render_copy_download(
            grocery_for_copy,
            label="Download list",
            key="grocery_copy",
            file_name="grocery-list.txt",
        )
    elif not excluded and not meal_names:
        st.warning("No grocery items found.")

    edit_count: int = result.get("edit_count", 0)
    if edit_count:
        st.caption(f"_{edit_count} ingredient edit(s) logged for later review._")

