"""Tests for recipe classification."""

from projects.grocery_wizard.classify import classify_column, classify_recipe

MEAL_OPTIONS = ["Drink", "Breakfast", "Lunch", "Dinner", "Snack", "Dessert"]


def test_meal_does_not_match_tea_inside_steamed() -> None:
    """Regression: 'tea' must not match inside words like 'steamed'."""
    ingredients = [
        "2 chicken breasts, steamed and sliced",
        "1 tbsp olive oil",
        "salt and pepper",
    ]
    result = classify_column(
        "Meal",
        "Chicken and Rice Bowl",
        ingredients,
        allowed_options=MEAL_OPTIONS,
    )
    assert result != "Drink"


def test_meal_classifies_dinner_from_pasta_title() -> None:
    result = classify_column(
        "Meal",
        "Creamy Tomato Pasta",
        ["8 oz spaghetti", "2 cloves garlic", "1 cup cream"],
        allowed_options=MEAL_OPTIONS,
    )
    assert result == "Dinner"


def test_meal_classifies_breakfast_from_title() -> None:
    result = classify_column(
        "Meal",
        "Blueberry Pancakes",
        ["1 cup flour", "2 eggs", "1 cup milk"],
        allowed_options=MEAL_OPTIONS,
    )
    assert result == "Breakfast"


def test_meal_returns_none_when_no_match() -> None:
    result = classify_column(
        "Meal",
        "Mystery Dish",
        ["item a", "item b"],
        allowed_options=MEAL_OPTIONS,
    )
    assert result is None


def test_meal_prefers_dinner_over_drink_when_both_could_match() -> None:
    result = classify_column(
        "Meal",
        "Dinner cocktail pasta",
        ["pasta", "tomato sauce"],
        allowed_options=MEAL_OPTIONS,
    )
    assert result == "Dinner"


def test_meal_classifies_actual_drink() -> None:
    result = classify_column(
        "Meal",
        "Strawberry Smoothie",
        ["1 cup strawberries", "1 cup yogurt", "1 tbsp honey"],
        allowed_options=MEAL_OPTIONS,
    )
    assert result == "Drink"


def test_classify_recipe_leaves_unmatched_meal_empty() -> None:
    result = classify_recipe(
        "Mystery Dish",
        ["item a", "item b"],
        [("Meal", "select", MEAL_OPTIONS)],
    )
    assert result["Meal"] is None
