"""Tests for meal planner filter logic and week plan persistence."""

from __future__ import annotations

import json
from pathlib import Path

from src.grocery_wizard.integrations.notion import ColumnInfo, DatabaseSchema, Recipe
from src.grocery_wizard.planning.meal_planner import (
    MealPlanFilters,
    _build_plan_interactive,
    _effective_top_k,
    _pick_weight,
    _recipe_normalized_ingredient_set,
    _review_plan_interactive,
    build_ingredient_index,
    default_filters,
    eligible_suggestion_pool,
    filter_recipes,
    fuzzy_match_recipes,
    load_recent_plan_names,
    parse_meal_requests,
    pick_diverse_recipe,
    recipe_matches_column_filter,
    replace_meals_in_plan,
    run_meal_planner,
    save_week_plan,
    select_diverse_meals,
    suggest_meals,
)


def _recipe(
    name: str,
    *,
    page_id: str | None = None,
    properties: dict | None = None,
    ingredients: str | None = None,
) -> Recipe:
    return Recipe(
        page_id=page_id or f"id-{name}",
        name=name,
        link=None,
        ingredients=ingredients,
        properties=properties or {},
    )


SCHEMA_COLUMNS = {
    "Meal": ColumnInfo(name="Meal", type="select", options=["Dinner", "Lunch"]),
    "Protein": ColumnInfo(
        name="Protein",
        type="multi_select",
        options=["Chicken", "Fish", "Tofu", "Beans"],
    ),
    "Dinner Category": ColumnInfo(
        name="Dinner Category",
        type="multi_select",
        options=["Curry", "Pasta", "Bowl", "Sheet Pan"],
    ),
    "Cuisine": ColumnInfo(
        name="Cuisine",
        type="multi_select",
        options=["Italian", "Asian", "Mexican"],
    ),
    "Dinner: Weeknight Friendly": ColumnInfo(
        name="Dinner: Weeknight Friendly",
        type="checkbox",
        options=[],
    ),
}


RECIPES = [
    _recipe(
        "Chicken Curry",
        properties={
            "Meal": "Dinner",
            "Protein": ["Chicken"],
            "Dinner: Weeknight Friendly": True,
        },
    ),
    _recipe(
        "Fish Tacos",
        properties={
            "Meal": "Dinner",
            "Protein": ["Fish"],
            "Dinner: Weeknight Friendly": False,
        },
    ),
    _recipe(
        "Tofu Bowl",
        properties={
            "Meal": "Lunch",
            "Protein": ["Tofu"],
            "Dinner: Weeknight Friendly": True,
        },
    ),
]


def test_select_filter_matches_exact_value() -> None:
    assert recipe_matches_column_filter("Dinner", "Dinner", "select")
    assert not recipe_matches_column_filter("Lunch", "Dinner", "select")


def test_multi_select_filter_matches_any_option() -> None:
    assert recipe_matches_column_filter(["Chicken", "Egg"], ["Chicken"], "multi_select")
    assert recipe_matches_column_filter(["Fish"], ["Chicken", "Fish"], "multi_select")
    assert not recipe_matches_column_filter(["Tofu"], ["Chicken"], "multi_select")
    assert not recipe_matches_column_filter(None, ["Chicken"], "multi_select")


def test_checkbox_filter_matches_bool() -> None:
    assert recipe_matches_column_filter(True, True, "checkbox")
    assert recipe_matches_column_filter(False, False, "checkbox")
    assert not recipe_matches_column_filter(False, True, "checkbox")


def test_filter_recipes_combines_columns() -> None:
    filters = MealPlanFilters(
        values={
            "Meal": "Dinner",
            "Protein": ["Chicken"],
            "Dinner: Weeknight Friendly": True,
        }
    )
    result = filter_recipes(RECIPES, filters, SCHEMA_COLUMNS)
    assert [recipe.name for recipe in result] == ["Chicken Curry"]


def test_filter_recipes_with_no_filters_returns_all() -> None:
    result = filter_recipes(RECIPES, MealPlanFilters(), SCHEMA_COLUMNS)
    assert len(result) == 3


def test_save_week_plan_writes_expected_json(tmp_path: Path) -> None:
    path = tmp_path / "week_plan.json"
    save_week_plan(["Pasta Primavera", "Banana Bread"], path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"recipes": ["Pasta Primavera", "Banana Bread"]}


def test_save_week_plan_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / ".local" / "grocery_wizard" / "week_plan.json"
    save_week_plan(["Soup"], path)
    assert path.exists()


def test_save_week_plan_strips_blank_names(tmp_path: Path) -> None:
    path = tmp_path / "week_plan.json"
    save_week_plan(["  Valid  ", "", "  "], path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["recipes"] == ["Valid"]


def test_default_filters_weeknight_dinner() -> None:
    filters = default_filters(SCHEMA_COLUMNS)
    assert filters.values == {
        "Meal": "Dinner",
        "Dinner: Weeknight Friendly": True,
    }


def test_default_filters_omits_missing_columns() -> None:
    minimal = {"Meal": SCHEMA_COLUMNS["Meal"]}
    filters = default_filters(minimal)
    assert filters.values == {"Meal": "Dinner"}


DIVERSITY_RECIPES = [
    _recipe(
        "Chicken Curry",
        page_id="id-1",
        properties={
            "Protein": ["Chicken"],
            "Dinner Category": ["Curry"],
            "Cuisine": ["Asian"],
        },
    ),
    _recipe(
        "Fish Pasta",
        page_id="id-2",
        properties={
            "Protein": ["Fish"],
            "Dinner Category": ["Pasta"],
            "Cuisine": ["Italian"],
        },
    ),
    _recipe(
        "Bean Bowl",
        page_id="id-3",
        properties={
            "Protein": ["Beans"],
            "Dinner Category": ["Bowl"],
            "Cuisine": ["Mexican"],
        },
    ),
    _recipe(
        "Tofu Sheet Pan",
        page_id="id-4",
        properties={
            "Protein": ["Tofu"],
            "Dinner Category": ["Sheet Pan"],
            "Cuisine": ["Asian"],
        },
    ),
    _recipe(
        "Chicken Pasta",
        page_id="id-5",
        properties={
            "Protein": ["Chicken"],
            "Dinner Category": ["Pasta"],
            "Cuisine": ["Italian"],
        },
    ),
]


def test_suggest_meals_locked_first_then_diverse(monkeypatch) -> None:
    dinner_recipes = [
        _recipe(
            "Chicken Curry",
            page_id="id-1",
            properties={
                "Meal": "Dinner",
                "Protein": ["Chicken"],
                "Dinner: Weeknight Friendly": True,
            },
        ),
        _recipe(
            "Fish Pasta",
            page_id="id-2",
            properties={
                "Meal": "Dinner",
                "Protein": ["Fish"],
                "Dinner: Weeknight Friendly": True,
            },
        ),
        _recipe(
            "Bean Bowl",
            page_id="id-3",
            properties={
                "Meal": "Dinner",
                "Protein": ["Beans"],
                "Dinner: Weeknight Friendly": True,
            },
        ),
    ]
    monkeypatch.setattr(
        "src.grocery_wizard.planning.meal_planner.select_diverse_meals",
        lambda pool, count, **kwargs: pool[:count],
    )
    plan = suggest_meals(
        dinner_recipes,
        meals=3,
        locked_names=["Bean Bowl"],
        schema_columns=SCHEMA_COLUMNS,
    )
    assert plan[0] == "Bean Bowl"
    assert len(plan) == 3
    assert plan[1:] == ["Chicken Curry", "Fish Pasta"]


def test_suggest_meals_uses_default_filters() -> None:
    plan = suggest_meals(
        RECIPES,
        meals=5,
        schema_columns=SCHEMA_COLUMNS,
    )
    assert plan == ["Chicken Curry"]


def test_suggest_meals_excludes_rejected_names() -> None:
    dinner_recipes = [
        _recipe(
            "Chicken Curry",
            page_id="id-1",
            properties={"Meal": "Dinner", "Dinner: Weeknight Friendly": True},
        ),
        _recipe(
            "Fish Pasta",
            page_id="id-2",
            properties={"Meal": "Dinner", "Dinner: Weeknight Friendly": True},
        ),
        _recipe(
            "Bean Bowl",
            page_id="id-3",
            properties={"Meal": "Dinner", "Dinner: Weeknight Friendly": True},
        ),
    ]
    plan = suggest_meals(
        dinner_recipes,
        meals=2,
        schema_columns=SCHEMA_COLUMNS,
        filters=MealPlanFilters(values={"Meal": "Dinner"}),
        rejected_names={"Chicken Curry", "Fish Pasta"},
        recent_names=set(),
    )
    assert plan == ["Bean Bowl"]


def test_load_recent_plan_names_reads_saved_plan(tmp_path: Path) -> None:
    path = tmp_path / "week_plan.json"
    save_week_plan(["Pasta", "Curry"], path)
    assert load_recent_plan_names(path) == {"Pasta", "Curry"}


def test_load_recent_plan_names_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_recent_plan_names(tmp_path / "missing.json") == set()


def test_effective_top_k_scales_with_pool_size() -> None:
    assert _effective_top_k(1) == 1
    assert _effective_top_k(3) == 3
    assert _effective_top_k(10) == 8
    assert _effective_top_k(40) == 15


def test_pick_weight_penalizes_recent_recipes() -> None:
    recent = {"Chicken Curry"}
    chicken = DIVERSITY_RECIPES[0]
    fish = DIVERSITY_RECIPES[1]
    assert _pick_weight(chicken, [], recent) < _pick_weight(fish, [], recent)


def test_replace_meals_in_plan_swaps_selected_slots(monkeypatch) -> None:
    pool = [
        _recipe("Chicken Curry", page_id="id-1"),
        _recipe("Fish Pasta", page_id="id-2"),
        _recipe("Bean Bowl", page_id="id-3"),
        _recipe("Tofu Stir Fry", page_id="id-4"),
    ]
    monkeypatch.setattr(
        "src.grocery_wizard.planning.meal_planner.pick_diverse_recipe",
        lambda candidates, selected, **kwargs: candidates[0],
    )

    updated, rejected = replace_meals_in_plan(
        ["Chicken Curry", "Fish Pasta", "Bean Bowl"],
        ["Fish Pasta"],
        all_recipes=pool,
        pool=pool,
    )

    assert rejected == {"Fish Pasta"}
    assert updated == ["Chicken Curry", "Tofu Stir Fry", "Bean Bowl"]


def test_select_diverse_meals_varies_protein_category_cuisine() -> None:
    selected = select_diverse_meals(DIVERSITY_RECIPES, 4)
    names = [recipe.name for recipe in selected]
    assert len(names) == 4
    assert len(set(names)) == 4

    proteins = [recipe.properties["Protein"][0] for recipe in selected]
    assert len(set(proteins)) >= 3  # pool has 4 protein types; random pick may repeat one

    categories = [recipe.properties["Dinner Category"][0] for recipe in selected]
    assert len(set(categories)) >= 3


def test_pick_diverse_recipe_avoids_back_to_back_protein() -> None:
    chicken_curry = DIVERSITY_RECIPES[0]
    chicken_pasta = DIVERSITY_RECIPES[4]
    fish_pasta = DIVERSITY_RECIPES[1]

    pick = pick_diverse_recipe(
        [chicken_pasta, fish_pasta],
        [chicken_curry],
    )
    assert pick.name == "Fish Pasta"


def test_pick_diverse_recipe_prefers_new_protein_over_repeat() -> None:
    chicken_curry = DIVERSITY_RECIPES[0]
    chicken_pasta = DIVERSITY_RECIPES[4]
    bean_bowl = DIVERSITY_RECIPES[2]

    pick = pick_diverse_recipe(
        [chicken_pasta, bean_bowl],
        [chicken_curry],
    )
    assert pick.name == "Bean Bowl"


def test_select_diverse_meals_relaxes_when_pool_small() -> None:
    small_pool = DIVERSITY_RECIPES[:2]
    selected = select_diverse_meals(small_pool, 5)
    assert len(selected) == 2
    assert {recipe.name for recipe in selected} == {
        "Chicken Curry",
        "Fish Pasta",
    }


def test_eligible_suggestion_pool_excludes_accepted_and_rejected() -> None:
    pool = DIVERSITY_RECIPES[:3]
    accepted = {"Chicken Curry"}
    rejected = {"Fish Pasta"}
    eligible = eligible_suggestion_pool(pool, accepted, rejected)
    assert [recipe.name for recipe in eligible] == ["Bean Bowl"]


def test_fuzzy_match_recipes_exact_case_insensitive() -> None:
    recipes = [_recipe("Chicken Curry"), _recipe("Fish Tacos")]
    assert [r.name for r in fuzzy_match_recipes("chicken curry", recipes)] == ["Chicken Curry"]


def test_fuzzy_match_recipes_substring() -> None:
    recipes = [_recipe("Chicken Curry"), _recipe("Fish Tacos")]
    assert {r.name for r in fuzzy_match_recipes("curry", recipes)} == {"Chicken Curry"}


def test_parse_meal_requests_splits_and_trims() -> None:
    assert parse_meal_requests("  Pasta ,  Curry  ,,") == ["Pasta", "Curry"]


def test_reject_suggests_different_recipe_same_slot(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.grocery_wizard.planning.meal_planner.pick_diverse_recipe",
        lambda candidates, selected, **kwargs: candidates[0],
    )
    pool = DIVERSITY_RECIPES[:3]
    prompts = iter(["r", "a"])
    plan = _build_plan_interactive(
        pool,
        1,
        schema=None,
        prompt_fn=lambda _: next(prompts),
    )
    assert plan == ["Fish Pasta"]
    assert plan[0] != "Chicken Curry"


def test_global_reject_excludes_from_later_slots(monkeypatch) -> None:
    def deterministic_pick(candidates, selected, **kwargs):
        order = ["Chicken Curry", "Fish Pasta", "Bean Bowl"]
        for name in order:
            for recipe in candidates:
                if recipe.name == name:
                    return recipe
        return candidates[0]

    monkeypatch.setattr(
        "src.grocery_wizard.planning.meal_planner.pick_diverse_recipe",
        deterministic_pick,
    )
    pool = DIVERSITY_RECIPES[:3]
    prompts = iter(["r", "a", "a"])
    plan = _build_plan_interactive(
        pool,
        2,
        schema=None,
        prompt_fn=lambda _: next(prompts),
    )
    assert plan == ["Fish Pasta", "Bean Bowl"]
    assert "Chicken Curry" not in plan


def test_review_plan_regenerates_single_slot(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.grocery_wizard.planning.meal_planner.pick_diverse_recipe",
        lambda candidates, selected, **kwargs: candidates[0],
    )
    pool = DIVERSITY_RECIPES[:4]
    rejected: set[str] = set()
    prompts = iter(["2", "a", ""])
    plan = _review_plan_interactive(
        ["Chicken Curry", "Fish Pasta", "Bean Bowl"],
        pool,
        all_recipes=pool,
        rejected_names=rejected,
        schema=None,
        prompt_fn=lambda _: next(prompts),
    )
    assert plan[0] == "Chicken Curry"
    assert plan[1] == "Tofu Sheet Pan"
    assert plan[2] == "Bean Bowl"


def test_review_plan_old_slot_not_auto_rejected(monkeypatch) -> None:
    """Regenerating a slot frees the old recipe unless user rejects it."""
    pool = DIVERSITY_RECIPES[:3]
    recipe_by_name = {recipe.name: recipe for recipe in pool}
    picks = iter([recipe_by_name["Bean Bowl"], recipe_by_name["Fish Pasta"]])

    def next_pick(candidates, selected, **kwargs):
        return next(picks)

    monkeypatch.setattr(
        "src.grocery_wizard.planning.meal_planner.pick_diverse_recipe",
        next_pick,
    )
    rejected: set[str] = set()
    prompts = iter(["1", "a", "2", "a", ""])
    plan = _review_plan_interactive(
        ["Chicken Curry", "Fish Pasta"],
        pool,
        all_recipes=pool,
        rejected_names=rejected,
        schema=None,
        prompt_fn=lambda _: next(prompts),
    )
    assert plan[0] == "Bean Bowl"
    assert plan[1] == "Fish Pasta"
    assert "Chicken Curry" not in rejected
    assert "Fish Pasta" not in rejected


def test_pick_diverse_recipe_samples_from_top_scorers() -> None:
    tied = [
        _recipe("Alpha", properties={"Protein": ["Chicken"], "Dinner Category": ["Pasta"]}),
        _recipe("Beta", properties={"Protein": ["Fish"], "Dinner Category": ["Curry"]}),
        _recipe("Gamma", properties={"Protein": ["Tofu"], "Dinner Category": ["Bowl"]}),
    ]
    picks = {pick_diverse_recipe(tied, []).name for _ in range(30)}
    assert picks == {"Alpha", "Beta", "Gamma"}


class _FakeDB:
    def __init__(self, recipes: list[Recipe]) -> None:
        self.schema = DatabaseSchema(
            name_column="Name",
            link_column="Link",
            ingredients_column="Ingredients",
            filter_columns=[SCHEMA_COLUMNS["Meal"], SCHEMA_COLUMNS["Protein"]],
            checkbox_columns=[SCHEMA_COLUMNS["Dinner: Weeknight Friendly"]],
            all_columns=SCHEMA_COLUMNS,
        )
        self._recipes = recipes

    def query_recipes(self) -> list[Recipe]:
        return list(self._recipes)


def _dinner_recipes(recipes: list[Recipe]) -> list[Recipe]:
    return [
        Recipe(
            page_id=recipe.page_id,
            name=recipe.name,
            link=recipe.link,
            ingredients=recipe.ingredients,
            properties={
                "Meal": "Dinner",
                "Dinner: Weeknight Friendly": True,
                **recipe.properties,
            },
        )
        for recipe in recipes
    ]


# ---------------------------------------------------------------------------
# Ingredient filter tests
# ---------------------------------------------------------------------------

_CHICKEN_RECIPE = _recipe(
    "Chicken Curry",
    page_id="id-cc",
    ingredients="1 lb chicken breast\n2 cups rice\n1 can coconut milk",
    properties={"Meal": "Dinner", "Dinner: Weeknight Friendly": True},
)
_FISH_RECIPE = _recipe(
    "Fish Tacos",
    page_id="id-ft",
    ingredients="2 fish fillets\n1 lime\n1/2 cup salsa",
    properties={"Meal": "Dinner", "Dinner: Weeknight Friendly": False},
)
_TOFU_RECIPE = _recipe(
    "Tofu Stir Fry",
    page_id="id-tf",
    ingredients="14 oz tofu\n2 tbsp soy sauce\n1 cup broccoli",
    properties={"Meal": "Dinner", "Dinner: Weeknight Friendly": True},
)
_EMPTY_RECIPE = _recipe(
    "Mystery Meal",
    page_id="id-mm",
    ingredients=None,
    properties={"Meal": "Dinner", "Dinner: Weeknight Friendly": True},
)

_INGREDIENT_RECIPES = [_CHICKEN_RECIPE, _FISH_RECIPE, _TOFU_RECIPE, _EMPTY_RECIPE]


def test_recipe_normalized_ingredient_set_parses_lines() -> None:
    result = _recipe_normalized_ingredient_set(_CHICKEN_RECIPE)
    assert "chicken breast" in result or any("chicken" in name for name in result)


def test_recipe_normalized_ingredient_set_empty_ingredients() -> None:
    result = _recipe_normalized_ingredient_set(_EMPTY_RECIPE)
    assert result == set()


def test_build_ingredient_index_keys_by_page_id() -> None:
    index = build_ingredient_index(_INGREDIENT_RECIPES)
    assert set(index.keys()) == {"id-cc", "id-ft", "id-tf", "id-mm"}
    assert index["id-mm"] == set()


def test_ingredient_filter_include_mode_matches_intersection() -> None:
    index = build_ingredient_index(_INGREDIENT_RECIPES)
    chicken_ingredients = index["id-cc"]
    assert chicken_ingredients, "Chicken recipe should have parsed ingredients"
    # Pick a known ingredient name from the chicken recipe
    sample_ingredient = next(iter(chicken_ingredients))

    filters = MealPlanFilters(
        values={},
        ingredient_names=[sample_ingredient],
        ingredient_mode="include",
    )
    result = filter_recipes(_INGREDIENT_RECIPES, filters, SCHEMA_COLUMNS, ingredient_index=index)
    result_names = {r.name for r in result}
    assert "Chicken Curry" in result_names
    # Mystery Meal has no ingredients → excluded in include mode
    assert "Mystery Meal" not in result_names


def test_ingredient_filter_include_mode_excludes_non_matching() -> None:
    index = build_ingredient_index(_INGREDIENT_RECIPES)
    filters = MealPlanFilters(
        values={},
        ingredient_names=["tofu"],
        ingredient_mode="include",
    )
    result = filter_recipes(_INGREDIENT_RECIPES, filters, SCHEMA_COLUMNS, ingredient_index=index)
    result_names = {r.name for r in result}
    assert "Tofu Stir Fry" in result_names
    assert "Chicken Curry" not in result_names
    assert "Fish Tacos" not in result_names
    assert "Mystery Meal" not in result_names


def test_ingredient_filter_exclude_mode_removes_matching() -> None:
    index = build_ingredient_index(_INGREDIENT_RECIPES)
    filters = MealPlanFilters(
        values={},
        ingredient_names=["tofu"],
        ingredient_mode="exclude",
    )
    result = filter_recipes(_INGREDIENT_RECIPES, filters, SCHEMA_COLUMNS, ingredient_index=index)
    result_names = {r.name for r in result}
    assert "Tofu Stir Fry" not in result_names
    assert "Chicken Curry" in result_names
    assert "Fish Tacos" in result_names
    # Mystery Meal has empty ingredients → no intersection → not excluded
    assert "Mystery Meal" in result_names


def test_ingredient_filter_empty_selection_returns_all() -> None:
    index = build_ingredient_index(_INGREDIENT_RECIPES)
    filters = MealPlanFilters(values={}, ingredient_names=[], ingredient_mode="include")
    result = filter_recipes(_INGREDIENT_RECIPES, filters, SCHEMA_COLUMNS, ingredient_index=index)
    assert len(result) == len(_INGREDIENT_RECIPES)


def test_ingredient_filter_stacks_with_column_filters() -> None:
    """Ingredient filter AND column filter must both be satisfied."""
    index = build_ingredient_index(_INGREDIENT_RECIPES)
    filters = MealPlanFilters(
        values={"Dinner: Weeknight Friendly": True},
        ingredient_names=["tofu"],
        ingredient_mode="include",
    )
    result = filter_recipes(_INGREDIENT_RECIPES, filters, SCHEMA_COLUMNS, ingredient_index=index)
    result_names = {r.name for r in result}
    # Tofu Stir Fry is weeknight-friendly and has tofu
    assert "Tofu Stir Fry" in result_names
    # Fish Tacos has no tofu
    assert "Fish Tacos" not in result_names


def test_ingredient_filter_include_excludes_empty_ingredient_recipes() -> None:
    """Recipes with missing/empty ingredients are excluded when include filter is active."""
    index = build_ingredient_index(_INGREDIENT_RECIPES)
    filters = MealPlanFilters(
        values={},
        ingredient_names=["rice"],
        ingredient_mode="include",
    )
    result = filter_recipes(_INGREDIENT_RECIPES, filters, SCHEMA_COLUMNS, ingredient_index=index)
    result_names = {r.name for r in result}
    assert "Mystery Meal" not in result_names


def test_ingredient_filter_without_precomputed_index() -> None:
    """filter_recipes falls back to on-the-fly parsing when no index is provided."""
    filters = MealPlanFilters(
        values={},
        ingredient_names=["tofu"],
        ingredient_mode="include",
    )
    result = filter_recipes(_INGREDIENT_RECIPES, filters, SCHEMA_COLUMNS)
    result_names = {r.name for r in result}
    assert "Tofu Stir Fry" in result_names
    assert "Chicken Curry" not in result_names


def test_run_meal_planner_with_requested_meals(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "src.grocery_wizard.planning.meal_planner.pick_diverse_recipe",
        lambda candidates, selected, **kwargs: candidates[0],
    )
    db = _FakeDB(_dinner_recipes(DIVERSITY_RECIPES))
    prompts = iter(
        [
            "5",
            "chicken curry, bean bowl",
            "",
            "a",
            "a",
            "a",
            "",
        ]
    )
    plan = run_meal_planner(
        db,
        meals=7,
        week_plan_path=tmp_path / "week_plan.json",
        prompt=lambda _: next(prompts),
        confirm=lambda _: True,
    )
    assert plan[:2] == ["Chicken Curry", "Bean Bowl"]
    assert len(plan) == 5
