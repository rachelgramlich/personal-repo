"""Keyword rules to infer select-column values from recipe text."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from src.grocery_wizard.recipes.weeknight import is_weeknight_friendly

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
        ],
        "Lunch": ["sandwich", "sandwiches"],
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
        "Snack/Side": ["snack", "appetizer", "dip", "bite", "side dish"],
        "Dessert": [
            "dessert",
            "cake",
            "cookie",
            "cookies",
            "brownie",
            "brownies",
            "pie",
            "pudding",
            "ice cream",
            "tart",
            "muffin",
            "muffins",
            "scone",
            "scones",
            "bars",
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
    "Snack/Side",
    "Dessert",
    "Drink",
)

# Legacy alias for databases that still use "Snack".
SNACK_SIDE_ALIASES: tuple[str, ...] = ("Snack/Side", "Snack")

# Savory titles that contain baking words but are not desserts.
SAVORY_MEAL_BLOCKERS = re.compile(
    r"\b("
    r"gnocchi|chile crisp|potpie|pot pie|samosa|quesadilla|taco|tofu|chicken|"
    r"beans|pasta|soup|stew|noodles|burrito|enchilada|lasagna|curry|"
    r"couscous|flatbread|fritters|meatball|satay|bibimbap|kimbap|adobo|ratatouille|"
    r"scallop|salmon|shrimp|halloumi|skewer|dumpling|tomato tart|potpie"
    r")\b",
    re.IGNORECASE,
)

DESSERT_PATTERN = re.compile(
    r"\b("
    r"cake|cakes|cookie|cookies|brownie|brownies|pudding|pavlova|shortcake|"
    r"gingerbread|crumble|galette|fluff|toffee|scones|scone|muffins|muffin|"
    r"cupcake|cupcakes|blondie|blondies|macaron|macaroon|fudge|truffle"
    r")\b",
    re.IGNORECASE,
)

DESSERT_CRISP_PATTERN = re.compile(r"\b(crisp|crumble)\b", re.IGNORECASE)
DESSERT_PIE_TART_PATTERN = re.compile(r"\b(pie|tart)\b", re.IGNORECASE)
DESSERT_BARS_PATTERN = re.compile(r"\b(bars)\b", re.IGNORECASE)

DRINK_PATTERN = re.compile(
    r"\b(smoothie|limeade|lemonade|mangonada|limonada|cocktail|mocktail|milkshake)\b",
    re.IGNORECASE,
)

BREAKFAST_PATTERN = re.compile(
    r"\b(pancake|pancakes|waffle|waffles|oatmeal|granola|frittata|omelet|omelette)\b",
    re.IGNORECASE,
)

SANDWICH_PATTERN = re.compile(r"\bsandwich(?:es)?\b", re.IGNORECASE)
SALAD_PATTERN = re.compile(r"\bsalad\b", re.IGNORECASE)

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
    *,
    total_minutes: float | None = None,
    weeknight_column: str | None = None,
) -> dict[str, Any]:
    """Return inferred values for each filter column (name, type, options)."""
    results: dict[str, Any] = {}
    meal_options: list[str] | None = None

    for column_name, column_type, options in filter_columns:
        value = classify_column(column_name, title, ingredients, allowed_options=options)
        if column_type == "multi_select" and value is not None:
            results[column_name] = [value]
        else:
            results[column_name] = value
        if column_name.lower() == "meal":
            meal_options = options

    meal = results.get("Meal")
    if meal is None:
        meal = classify_column("Meal", title, ingredients, allowed_options=meal_options)

    if weeknight_column:
        results[weeknight_column] = is_weeknight_friendly(
            title,
            meal=meal if isinstance(meal, str) else None,
            total_minutes=total_minutes,
        )

    return results


def _classify_meal(
    text: str,
    rules: dict[str, list[str]],
    allowed_options: list[str] | None,
) -> str | None:
    structured = _classify_meal_structured(text)
    if structured is not None:
        return _resolve_meal_option(structured, allowed_options)

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
                return _resolve_meal_option(candidate, allowed_options)
    return None


def _classify_meal_structured(text: str) -> str | None:
    """Rule-based meal classification with explicit priority."""
    if _is_dessert(text):
        return "Dessert"

    if BREAKFAST_PATTERN.search(text):
        return "Breakfast"

    if SANDWICH_PATTERN.search(text):
        return "Lunch"

    if SALAD_PATTERN.search(text):
        return "Snack/Side"

    if _score_keywords(CLASSIFICATION_RULES["meal"]["Snack/Side"], text) > 0:
        return "Snack/Side"

    if SAVORY_MEAL_BLOCKERS.search(text):
        return "Dinner"

    if _score_keywords(CLASSIFICATION_RULES["meal"]["Dinner"], text) > 0:
        return "Dinner"

    if DRINK_PATTERN.search(text):
        return "Drink"

    return None


def _is_dessert(text: str) -> bool:
    if SAVORY_MEAL_BLOCKERS.search(text):
        if DESSERT_CRISP_PATTERN.search(text) and not SAVORY_MEAL_BLOCKERS.search(text):
            pass
        else:
            return False

    if DESSERT_PATTERN.search(text):
        return True

    if DESSERT_CRISP_PATTERN.search(text):
        return True

    if DESSERT_PIE_TART_PATTERN.search(text):
        if "pot" in text or "chicken" in text or "tomato" in text:
            return False
        return True

    if DESSERT_BARS_PATTERN.search(text) and not SAVORY_MEAL_BLOCKERS.search(text):
        return True

    return False


def _resolve_meal_option(meal: str, allowed_options: list[str] | None) -> str | None:
    if allowed_options is None:
        return meal
    if meal in allowed_options:
        return meal
    if meal == "Snack/Side" and "Snack" in allowed_options:
        return "Snack"
    if meal == "Snack" and "Snack/Side" in allowed_options:
        return "Snack/Side"
    return None


def _score_keywords(keywords: list[str], text: str) -> int:
    return sum(1 for keyword in keywords if _keyword_matches(keyword, text))


def _keyword_matches(keyword: str, text: str) -> bool:
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


def _normalize_text(title: str, ingredients: Iterable[str]) -> str:
    combined = title + " " + " ".join(ingredients)
    return re.sub(r"\s+", " ", combined.lower()).strip()
