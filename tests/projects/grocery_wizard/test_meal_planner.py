"""Tests for meal planner filter logic and week plan persistence."""

from __future__ import annotations

import json
from pathlib import Path

from projects.grocery_wizard.meal_planner import (
    MealPlanFilters,
    _build_plan_interactive,
    _review_plan_interactive,
    default_filters,
    eligible_suggestion_pool,
    filter_recipes,
    fuzzy_match_recipes,
    parse_meal_requests,
    pick_diverse_recipe,
    recipe_matches_column_filter,
    run_meal_planner,
    save_week_plan,
    select_diverse_meals,
)
from projects.grocery_wizard.notion import ColumnInfo, DatabaseSchema, Recipe


def _recipe(
    name: str,
    *,
    page_id: str | None = None,
    properties: dict | None = None,
) -> Recipe:
    return Recipe(
        page_id=page_id or f"id-{name}",
        name=name,
        link=None,
        ingredients=None,
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
        "projects.grocery_wizard.meal_planner.pick_diverse_recipe",
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
        "projects.grocery_wizard.meal_planner.pick_diverse_recipe",
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
        "projects.grocery_wizard.meal_planner.pick_diverse_recipe",
        lambda candidates, selected, **kwargs: candidates[0],
    )
    pool = DIVERSITY_RECIPES[:4]
    rejected: set[str] = set()
    prompts = iter(["2", "a", ""])
    plan = _review_plan_interactive(
        ["Chicken Curry", "Fish Pasta", "Bean Bowl"],
        pool,
        pool,
        rejected,
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
        "projects.grocery_wizard.meal_planner.pick_diverse_recipe",
        next_pick,
    )
    rejected: set[str] = set()
    prompts = iter(["1", "a", "2", "a", ""])
    plan = _review_plan_interactive(
        ["Chicken Curry", "Fish Pasta"],
        pool,
        pool,
        rejected,
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


def test_run_meal_planner_with_requested_meals(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "projects.grocery_wizard.meal_planner.pick_diverse_recipe",
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
