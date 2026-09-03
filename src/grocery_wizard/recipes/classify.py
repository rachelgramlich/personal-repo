"""Keyword rules to infer select-column values from recipe text."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Column name (lowercase) -> option -> keywords
# Options must match the user's Notion database (see README / plan).
CLASSIFICATION_RULES: dict[str, dict[str, list[str]]] = {
    "protein": {
        "Chicken": ["chicken", "poultry", "turkey"],
        "Fish": [
            "salmon",
            "fish",
            "cod",
            "tuna",
            "shrimp",
            "seafood",
            "scallop",
            "crab",
            "lobster",
            "halibut",
            "tilapia",
            "trout",
        ],
        "Tofu": ["tofu", "tempeh"],
        "Beans": ["bean", "beans", "chickpea", "lentil", "legume"],
        "Egg": ["egg", "frittata", "omelet", "omelette"],
        "Dairy": ["cheese", "milk", "cream", "yogurt", "butter", "feta", "parmesan"],
        "Veg": ["vegetable", "vegetarian", "veggie", "salad", "zucchini", "asparagus"],
    },
    "meal": {
        "Breakfast": [
            "breakfast",
            "pancake",
            "pancakes",
            "waffle",
            "waffles",
            "oatmeal",
            "granola",
            "frittata",
            "omelet",
            "omelette",
            "muffin",
            "muffins",
        ],
        "Lunch": ["lunch", "sandwich", "wrap", "salad bowl"],
        "Dinner": [
            "dinner",
            "curry",
            "roast",
            "stew",
            "casserole",
            "pasta",
            "entree",
            "main course",
        ],
        "Snack": ["snack", "appetizer", "dip", "bite"],
        "Dessert": [
            "dessert",
            "cake",
            "cookie",
            "brownie",
            "pie",
            "pudding",
            "ice cream",
        ],
        "Drink": [
            "beverage",
            "limeade",
            "lemonade",
            "smoothie",
            "cocktail",
            "mocktail",
            "milkshake",
        ],
    },
    "cuisine": {
        "Italian": ["italian", "pasta", "risotto", "parmesan", "marinara"],
        "Mexican": ["mexican", "taco", "burrito", "enchilada", "salsa", "cilantro"],
        "Asian": ["asian", "soy sauce", "miso", "ginger", "sesame", "ramen", "stir fry"],
        "Indian": ["indian", "curry", "tikka", "masala", "naan", "garam masala"],
        "Mediterranean": ["mediterranean", "feta", "olive", "hummus", "tzatziki"],
        "American": ["american", "bbq", "burger", "mac and cheese"],
        "Japanese": ["japanese", "miso", "teriyaki", "udon", "soba"],
        "Middle Eastern": ["tahini", "shawarma", "falafel", "harissa"],
        "French": ["french", "béchamel", "bechamel", "croissant", "baguette"],
    },
    "dinner category": {
        "Curry": ["curry"],
        "Taco / Burrito": ["taco", "burrito"],
        "Bowl": ["bowl", "grain bowl", "rice bowl"],
        "Grilled": ["grill", "grilled"],
        "Sheet Pan": ["sheet pan"],
        "One-Pot / One-Pan": ["one pot", "one-pot", "one pan", "one-pan", "skillet"],
        "Casserole / Bake": ["casserole", "bake", "baked"],
        "Stir Fry": ["stir fry", "stir-fry"],
        "Pasta": ["pasta", "spaghetti", "penne", "linguine"],
        "Sandwich / Wrap": ["sandwich", "wrap", "burger"],
        "Salad": ["salad"],
        "Soup / Stew": ["soup", "stew", "chili"],
    },
    "difficulty": {
        "Easy": ["easy", "simple", "quick", "5 minute", "10 minute"],
        "Medium": ["medium"],
        "Hard": ["hard", "advanced", "complex"],
    },
    "tags": {
        "Weeknight": ["weeknight", "quick", "30 minute", "easy"],
        "Healthy": ["healthy", "light", "lean"],
        "Cozy": ["cozy", "comfort"],
        "Meal Prep": ["meal prep", "batch"],
        "Entertaining": ["entertaining", "dinner party", "company"],
    },
}

# When multiple meal keywords match, prefer savory meals over drinks.
MEAL_PRIORITY: tuple[str, ...] = (
    "Breakfast",
    "Lunch",
    "Dinner",
    "Snack",
    "Dessert",
    "Drink",
)


def classify_column(
    column_name: str,
    title: str,
    ingredients: Iterable[str],
    allowed_options: list[str] | None = None,
) -> str | None:
    text = _normalize_text(title, ingredients)
    rules = CLASSIFICATION_RULES.get(column_name.lower(), {})

    if column_name.lower() == "meal":
        return _classify_meal(text, rules, allowed_options)

    best_option: str | None = None
    best_score = 0

    for option, keywords in rules.items():
        if allowed_options and option not in allowed_options:
            continue
        score = _score_keywords(keywords, text)
        if score > best_score:
            best_score = score
            best_option = option

    if best_option:
        return best_option

    if allowed_options and len(allowed_options) == 1:
        return allowed_options[0]

    return None


def classify_recipe(
    title: str,
    ingredients: list[str],
    filter_columns: list[tuple[str, str, list[str]]],
) -> dict[str, str | list[str] | None]:
    """Return inferred values for each filter column (name, type, options)."""
    results: dict[str, str | list[str] | None] = {}
    for column_name, column_type, options in filter_columns:
        value = classify_column(column_name, title, ingredients, allowed_options=options)
        if column_type == "multi_select" and value is not None:
            results[column_name] = [value]
        else:
            results[column_name] = value
    return results


def _classify_meal(
    text: str,
    rules: dict[str, list[str]],
    allowed_options: list[str] | None,
) -> str | None:
    scored: list[tuple[str, int]] = []
    for option in MEAL_PRIORITY:
        keywords = rules.get(option)
        if not keywords:
            continue
        if allowed_options and option not in allowed_options:
            continue
        score = _score_keywords(keywords, text)
        if score > 0:
            scored.append((option, score))

    if not scored:
        return None

    best_score = max(score for _, score in scored)
    for option in MEAL_PRIORITY:
        for candidate, score in scored:
            if candidate == option and score == best_score:
                return candidate
    return None


def _score_keywords(keywords: list[str], text: str) -> int:
    return sum(1 for keyword in keywords if _keyword_matches(keyword, text))


def _keyword_matches(keyword: str, text: str) -> bool:
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


def _normalize_text(title: str, ingredients: Iterable[str]) -> str:
    combined = title + " " + " ".join(ingredients)
    return re.sub(r"\s+", " ", combined.lower()).strip()
