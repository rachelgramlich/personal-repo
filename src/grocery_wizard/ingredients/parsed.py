"""Ingredient-parser integration for cleaned grocery-ingredient lines."""

from __future__ import annotations

__all__ = [
    "aggregate_amounts",
    "ingredient_name",
    "parse_amount",
    "parse_stored_ingredient",
    "should_show_amount",
]

import math
import re
from fractions import Fraction
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from ingredient_parser import parse_ingredient

if TYPE_CHECKING:
    from ingredient_parser.dataclasses import IngredientAmount, ParsedIngredient

_nltk_ready = False

_LEADING_QTY_RE = re.compile(
    r"^((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s*",
)

_AMOUNT_STR_RE = re.compile(
    r"^((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s*(.*)\Z",
    re.DOTALL,
)

_UNICODE_DASHES = ("–", "—", "−")  # noqa: RUF001
_UNICODE_FRACTIONS = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
    "⅓": "1/3",
    "⅔": "2/3",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}

_VOLUME_UNITS = frozenset(
    {
        "teaspoon",
        "teaspoons",
        "tsp",
        "tablespoon",
        "tablespoons",
        "tbsp",
        "cup",
        "cups",
        "milliliter",
        "milliliters",
        "ml",
        "liter",
        "liters",
        "l",
        "pinch",
        "pinches",
        "dash",
        "dashes",
        "gram",
        "grams",
        "g",
        "kilogram",
        "kilograms",
        "kg",
    }
)

_COUNT_UNITS = frozenset(
    {
        "clove",
        "cloves",
        "head",
        "heads",
        "bunch",
        "bunches",
        "sprig",
        "sprigs",
        "slice",
        "slices",
        "piece",
        "pieces",
        "can",
        "cans",
        "package",
        "packages",
        "pkg",
        "stick",
        "sticks",
        "bag",
        "bags",
        "jar",
        "jars",
        "box",
        "boxes",
        "container",
        "containers",
        "packet",
        "packets",
        "sheet",
        "sheets",
        "leaf",
        "leaves",
        "stalk",
        "stalks",
        "ounce",
        "ounces",
        "oz",
        "pound",
        "pounds",
        "lb",
        "lbs",
    }
)

_PRESERVED_PRODUCTS = (
    "crushed red pepper",
    "red pepper flakes",
    "tomato paste",
    "tomato sauce",
    "coconut milk",
    "chicken broth",
    "chicken stock",
    "vegetable broth",
    "vegetable stock",
)

_UNIT_CANONICAL: dict[str, str] = {
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsp": "tbsp",
    "tbsps": "tbsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsp": "tsp",
    "tsps": "tsp",
    "cup": "cup",
    "cups": "cup",
    "ounce": "oz",
    "ounces": "oz",
    "oz": "oz",
    "pound": "lb",
    "pounds": "lb",
    "lb": "lb",
    "lbs": "lb",
    "gram": "g",
    "grams": "g",
    "g": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kg": "kg",
    "milliliter": "ml",
    "milliliters": "ml",
    "ml": "ml",
    "liter": "l",
    "liters": "l",
    "l": "l",
    "pinch": "pinch",
    "pinches": "pinch",
    "dash": "dash",
    "dashes": "dash",
    "clove": "clove",
    "cloves": "clove",
    "head": "head",
    "heads": "head",
    "bunch": "bunch",
    "bunches": "bunch",
    "sprig": "sprig",
    "sprigs": "sprig",
    "slice": "slice",
    "slices": "slice",
    "piece": "piece",
    "pieces": "piece",
    "can": "can",
    "cans": "can",
    "package": "pkg",
    "packages": "pkg",
    "pkg": "pkg",
    "stick": "stick",
    "sticks": "stick",
    "bag": "bag",
    "bags": "bag",
    "jar": "jar",
    "jars": "jar",
    "box": "box",
    "boxes": "box",
    "container": "container",
    "containers": "container",
    "packet": "packet",
    "packets": "packet",
    "sheet": "sheet",
    "sheets": "sheet",
    "leaf": "leaf",
    "leaves": "leaf",
    "stalk": "stalk",
    "stalks": "stalk",
}

_UNIT_DISPLAY: dict[str, tuple[str, str]] = {
    "tsp": ("tsp", "tsp"),
    "tbsp": ("tbsp", "tbsp"),
    "cup": ("cup", "cups"),
    "oz": ("oz", "oz"),
    "lb": ("lb", "lb"),
    "g": ("g", "g"),
    "kg": ("kg", "kg"),
    "ml": ("ml", "ml"),
    "l": ("l", "l"),
    "pinch": ("pinch", "pinches"),
    "dash": ("dash", "dashes"),
    "clove": ("clove", "cloves"),
    "head": ("head", "heads"),
    "bunch": ("bunch", "bunches"),
    "sprig": ("sprig", "sprigs"),
    "slice": ("slice", "slices"),
    "piece": ("piece", "pieces"),
    "can": ("can", "cans"),
    "pkg": ("pkg", "pkgs"),
    "stick": ("stick", "sticks"),
    "bag": ("bag", "bags"),
    "jar": ("jar", "jars"),
    "box": ("box", "boxes"),
    "container": ("container", "containers"),
    "packet": ("packet", "packets"),
    "sheet": ("sheet", "sheets"),
    "leaf": ("leaf", "leaves"),
    "stalk": ("stalk", "stalks"),
}

_PLURALS: dict[str, str] = {
    "egg": "eggs",
    "tomato": "tomatoes",
    "potato": "potatoes",
    "onion": "onions",
    "carrot": "carrots",
    "mushroom": "mushrooms",
    "lemon": "lemons",
    "lime": "limes",
    "apple": "apples",
    "banana": "bananas",
    "avocado": "avocados",
    "scallion": "scallions",
    "shallot": "shallots",
}

_HIDE_AMOUNT_UNITS_RE = re.compile(
    r"\b(tsp|teaspoons?|tbsp|tablespoons?|cups?|packed|ounces?|oz)\b",
    re.IGNORECASE,
)

_TRAILING_CLAUSE_RE = re.compile(
    r"\b(?:plus more for|plus more\b|such as|or to taste|to taste|for garnish|optional|"
    r"as needed|if needed|for serving|for topping|to serve)\b.*",
    re.IGNORECASE,
)

_TRAILING_MORE_RE = re.compile(r"\s+more$", re.IGNORECASE)

_OR_ALTERNATIVE_RE = re.compile(r"\s+or\s+", re.IGNORECASE)

_INLINE_OZ_CAN_RE = re.compile(r"\d+\s*oz\s+(can|cans)\b", re.IGNORECASE)

_WEIGHT_UNITS_STRIP_AT_STORAGE = frozenset(
    {"oz", "ounce", "ounces", "g", "gram", "grams", "kg", "kilogram", "kilograms"}
)

_LEMON_LINE_RE = re.compile(
    r"^(?:juice|zest|grated zest) of\s+",
    re.IGNORECASE,
)

_LEMON_ZEST_LEGACY_RE = re.compile(
    r"^(?:\d+(?:\s+\d+/\d+|\d+/\d+|\.\d+)?\s+)?"
    r"(?:(?:finely|freshly)\s+)?(?:grated\s+)?lemon\s+zest\b",
    re.IGNORECASE,
)

_FROM_LEMON_RE = re.compile(
    r"\(from\s+(half(?:\s+a)?|(?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s+lemons?\)",
    re.IGNORECASE,
)

_SUBSTITUTION_PAREN_RE = re.compile(
    r"\((?:or\s+)?(?:substitute|see notes|frozen|fresh)\b",
    re.IGNORECASE,
)

_TO_TASTE_RE = re.compile(r"\bto taste\b", re.IGNORECASE)

_PREP_TRAILING_RE = re.compile(
    r",\s*(?:"
    r"beaten|chopped|diced|minced|sliced|grated|shredded|crushed|peeled|seeded|cored|"
    r"trimmed|halved|quartered|julienned|cubed|mashed|softened|melted|thawed|rinsed|drained|"
    r"juiced|zested|"
    r"smashed(?:\s+and\s+peeled)?|peeled\s+and\s+grated|minced\s+or\s+grated"
    r")(?:\s+.*)?$",
    re.IGNORECASE,
)

# Parenthetical prep instructions (not product descriptors like ``(15-ounce)``).
_PREP_PAREN_RE = re.compile(
    r"\([^)]*(?:"
    r"torn|cut\s+into|diced|chopped|minced|sliced|grated|peeled|seeded|"
    r"bite[- ]size|into\s+\w+\s+pieces|reserve\s+the|optional"
    r")[^)]*\)",
    re.IGNORECASE,
)


def _needs_display_prep_strip(text: str) -> bool:
    return bool(_PREP_TRAILING_RE.search(text) or _PREP_PAREN_RE.search(text))


def _strip_prep_parenthetical_notes(text: str) -> str:
    return _PREP_PAREN_RE.sub("", text).strip()


def is_nyt_cooking_url(url: str | None) -> bool:
    """Return True when *url* points at NYT Cooking."""
    if not url:
        return False
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    return host.endswith("cooking.nytimes.com") or (
        "nytimes.com" in host and "/recipes/" in parsed.path
    )


def _ensure_nltk_data() -> None:
    global _nltk_ready  # noqa: PLW0603
    if _nltk_ready:
        return
    try:
        import nltk

        nltk.data.find("taggers/averaged_perceptron_tagger_eng")
    except LookupError:
        import nltk

        nltk.download("averaged_perceptron_tagger_eng", quiet=True)
    _nltk_ready = True


def _normalize_unicode(text: str) -> str:
    for dash in _UNICODE_DASHES:
        text = text.replace(dash, "-")
    for char, replacement in _UNICODE_FRACTIONS.items():
        text = text.replace(char, replacement)
    return text


def _strip_optional_prefix(text: str) -> str:
    return re.sub(r"^optional:\s*", "", text, flags=re.IGNORECASE).strip()


def _strip_or_prefix(text: str) -> str:
    if text.lower().startswith("or "):
        return text[3:].strip()
    return text


def _fraction_to_float(value: Fraction | str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, Fraction):
        return float(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"half", "a half"}:
            return 0.5
        if "/" in lowered:
            return _parse_qty(lowered)
        try:
            return float(lowered)
        except ValueError:
            return None
    return float(value)


def _parse_qty(value: str) -> float:
    text = value.strip()
    if " " in text:
        whole, frac = text.split(None, 1)
        return float(whole) + _parse_qty(frac)
    if "/" in text:
        num, denom = text.split("/", 1)
        return float(num) / float(denom)
    return float(text)


def _format_qty(qty: float) -> str:
    if qty == int(qty):
        return str(int(qty))
    whole = int(qty)
    frac = qty - whole
    for num, denom in ((1, 4), (1, 3), (1, 2), (2, 3), (3, 4)):
        if abs(frac - num / denom) < 0.005:
            if whole:
                return f"{whole} {num}/{denom}"
            return f"{num}/{denom}"
    return f"{qty:.2f}".rstrip("0").rstrip(".")


def _unit_key(unit: str | None) -> str | None:
    if unit is None:
        return None
    cleaned = unit.strip().lower().rstrip(".")
    if not cleaned:
        return None
    return _UNIT_CANONICAL.get(cleaned, cleaned)


def _is_volume_unit(unit: str | None) -> bool:
    if unit is None:
        return False
    canonical = _unit_key(unit)
    return canonical in {"tsp", "tbsp", "cup", "ml", "l", "pinch", "dash"}


def _is_weight_unit_strip_at_storage(unit: str | None) -> bool:
    if unit is None:
        return False
    canonical = _unit_key(unit)
    return canonical in _WEIGHT_UNITS_STRIP_AT_STORAGE


def _has_inline_oz_before_can(original: str) -> bool:
    return bool(_INLINE_OZ_CAN_RE.search(original))


def _is_count_unit(unit: str | None) -> bool:
    if unit is None:
        return False
    return unit.strip().lower().rstrip(".") in _COUNT_UNITS


def _display_unit(canonical: str, qty: float) -> str:
    singular, plural = _UNIT_DISPLAY.get(canonical, (canonical, f"{canonical}s"))
    return plural if qty > 1 else singular


def _first_alternative(name: str) -> str:
    if " or " not in name.lower():
        return name.strip()
    if re.search(r"\bor\b.*\b(?:stock|broth)\b", name, re.IGNORECASE):
        return name.strip()
    parts = [part.strip() for part in _OR_ALTERNATIVE_RE.split(name.strip()) if part.strip()]
    if not parts:
        return name.strip()
    return max(parts, key=lambda part: len(part.split()))


def _match_preserved_product(name: str) -> str | None:
    lowered = name.lower()
    if re.search(r"\bor\b.*\b(?:stock|broth)\b", lowered):
        return None
    for product in sorted(_PRESERVED_PRODUCTS, key=len, reverse=True):
        if product in lowered:
            return product
    # ground meats (not ground pepper/spices)
    ground_match = re.search(r"\bground\s+([a-z]+)", lowered)
    if ground_match and "pepper" not in lowered:
        return f"ground {ground_match.group(1)}"
    frozen_match = re.search(r"\bfrozen\s+([a-z]+(?:\s+[a-z]+)?)", lowered)
    if frozen_match:
        return f"frozen {frozen_match.group(1)}"
    for form in ("diced", "crushed", "stewed", "fire-roasted", "whole peeled", "whole"):
        if re.search(rf"\b{re.escape(form)}\s+tomatoes?\b", lowered):
            if form == "whole peeled":
                return "whole peeled tomatoes"
            return f"{form} tomatoes"
    return None


def _is_garlic_name(name: str) -> bool:
    return name.strip().lower() == "garlic"


def _is_garlic_clove_unit(unit: str | None, name: str) -> bool:
    return _is_garlic_name(name) and _unit_key(unit or "") == "clove"


def garlic_clove_count_from_line(line: str) -> float | None:
    """Return the clove count from a raw garlic-clove ingredient line, if any."""
    text = _strip_parenthetical_notes(
        _strip_or_prefix(_strip_optional_prefix(_normalize_unicode(line.strip())))
    )
    if not text:
        return None

    match = _GARLIC_CLOVE_LINE_RE.match(text)
    if match:
        return _parse_qty(match.group(1))

    parsed = _parse_with_library(text)
    if not parsed.name:
        return None
    name = _simplify_parsed_name(parsed.name[0].text)
    if not _is_garlic_name(name):
        return None
    selected = _select_amount(list(parsed.amount or []), text)
    if selected is None:
        return None
    unit = _unit_key(_amount_unit(selected))
    if unit != "clove":
        return None
    return _amount_quantity(selected)


def _prefer_plural_form(name: str) -> str:
    words = name.split()
    if not words:
        return name
    last = words[-1].lower()
    if last in _PLURALS:
        words[-1] = _PLURALS[last]
        return " ".join(words)
    if last == "garlic" and len(words) > 1 and words[0].lower() in {"clove", "cloves"}:
        return "garlic"
    return name


_FLOUR_TYPE_RE = re.compile(
    r"\b(?:all[\s-]?purpose|bread|cake|pastry|self[\s-]?raising|self[\s-]?rising)\s+flour\b",
    re.IGNORECASE,
)


def _simplify_parsed_name(name: str) -> str:
    cleaned = _first_alternative(name.strip())
    cleaned = re.sub(r"\([^)]*\)", "", cleaned).strip()
    cleaned = _TRAILING_CLAUSE_RE.sub("", cleaned).strip()
    cleaned = _TRAILING_MORE_RE.sub("", cleaned).strip(" ,")
    preserved = _match_preserved_product(cleaned)
    if preserved:
        return preserved
    if _FLOUR_TYPE_RE.search(cleaned):
        return "flour"
    lowered = cleaned.lower()
    if lowered in {"lemon", "lemons", "lemon wedges"}:
        return "lemons"
    if lowered in {"lime", "limes", "lime wedges"}:
        return "limes"
    if lowered.endswith(" leaves"):
        return lowered.replace(" leaves", "")
    if lowered.startswith("freshly ground "):
        cleaned = cleaned[15:].strip()
    elif lowered.startswith("ground ") and "pepper" in lowered:
        cleaned = cleaned[7:].strip()
    elif lowered.startswith("fresh "):
        cleaned = cleaned[6:].strip()
    words = cleaned.split()
    while words and words[0].lower() in _DESCRIPTOR_WORDS:
        words.pop(0)
    cleaned = " ".join(words)
    return _prefer_plural_form(cleaned)


def _flatten_amounts(amounts: list[IngredientAmount]) -> list[IngredientAmount]:
    """Expand composite amounts (e.g. ``1 tsp plus 1/4 cup``) into flat parts."""
    flattened: list[IngredientAmount] = []
    for amount in amounts:
        nested = getattr(amount, "amounts", None)
        if nested:
            flattened.extend(nested)
        else:
            flattened.append(amount)
    return flattened


def _amount_unit(amount: IngredientAmount) -> str:
    return str(getattr(amount, "unit", None) or "").strip()


def _amount_quantity(amount: IngredientAmount) -> float | None:
    if getattr(amount, "RANGE", False):
        low = _fraction_to_float(amount.quantity)
        high = _fraction_to_float(amount.quantity_max)
        if low is None and high is None:
            return None
        if low is None:
            return high
        if high is None:
            return low
        return max(low, high)
    return _fraction_to_float(amount.quantity)


def _amounts_from_original_context(
    amounts: list[IngredientAmount],
    original: str,
) -> list[IngredientAmount]:
    """Drop amounts that only appear inside parenthetical weight notes."""
    amounts = _flatten_amounts(amounts)
    if "(" not in original:
        return amounts
    paren_chunks = re.findall(r"\([^)]*\)", original)
    paren_text = " ".join(paren_chunks).lower()
    filtered: list[IngredientAmount] = []
    for amount in amounts:
        text = str(getattr(amount, "text", "") or "").lower()
        if text and text in paren_text and _is_count_unit(_amount_unit(amount)) is False:
            unit = _amount_unit(amount).lower()
            if unit in {
                "pound",
                "pounds",
                "lb",
                "lbs",
                "ounce",
                "ounces",
                "oz",
                "gram",
                "grams",
                "g",
            }:
                continue
        filtered.append(amount)
    return filtered or amounts


def _include_size_in_name(parsed: ParsedIngredient, name: str) -> str:
    if parsed.size is None:
        return name
    if len(parsed.amount or []) > 1:
        return name
    if name.lower() in {"egg", "eggs"}:
        return _prefer_plural_form(name)
    size = parsed.size.text.strip().rstrip(",")
    if not size or re.search(r"\bor\b", size, re.IGNORECASE):
        return name
    if size.lower() in name.lower():
        return name
    return f"{size} {name}".strip()


def _strip_size_descriptors(name: str) -> str:
    words = name.split()
    while words and words[0].lower().rstrip(",") in _SIZE_WORDS:
        words.pop(0)
    return " ".join(words) if words else name


def _format_with_descriptor_unit(qty: float, unit: str, name: str) -> str:
    canonical = _unit_key(unit)
    if canonical is None:
        return f"{_format_qty(qty)} {name}".strip()
    display = _display_unit(canonical, qty)
    if canonical == "head" and _is_garlic_name(name):
        return f"{_format_qty(qty)} head garlic"
    if canonical in {"can", "pkg", "jar", "box", "bag"}:
        return f"{_format_qty(qty)} {display} {name}".strip()
    if display in name.lower().split():
        return f"{_format_qty(qty)} {name}".strip()
    return f"{_format_qty(qty)} {name} {display}".strip()


def _select_amount(amounts: list[IngredientAmount], original: str = "") -> IngredientAmount | None:
    if not amounts:
        return None

    amounts = _amounts_from_original_context(amounts, original)

    if len(amounts) > 1:
        comparable = [amount for amount in amounts if _amount_quantity(amount) is not None]
        if comparable:
            return max(comparable, key=lambda amount: _amount_quantity(amount) or 0.0)

    bare_counts = [amount for amount in amounts if not _amount_unit(amount)]
    if bare_counts:
        return max(bare_counts, key=lambda amount: _amount_quantity(amount) or 0.0)

    count_amounts = [amount for amount in amounts if _is_count_unit(_amount_unit(amount))]
    if count_amounts:
        weight_amounts = [
            amount for amount in amounts if _is_weight_unit_strip_at_storage(_amount_unit(amount))
        ]
        if weight_amounts:
            return max(count_amounts, key=lambda amount: _amount_quantity(amount) or 0.0)
        return max(count_amounts, key=lambda amount: _amount_quantity(amount) or 0.0)

    non_volume = [
        amount
        for amount in amounts
        if not _is_volume_unit(_amount_unit(amount)) and _amount_unit(amount)
    ]
    if non_volume:
        return max(non_volume, key=lambda amount: _amount_quantity(amount) or 0.0)

    return amounts[0]


def _append_unit_to_name(name: str, unit: str, qty: float) -> str:
    canonical = _unit_key(unit)
    if canonical is None:
        return name
    if canonical == "clove" and "garlic" in name.lower():
        return name
    display = _display_unit(canonical, qty)
    if name.lower().endswith(f" {display}"):
        return name
    if display in name.lower().split():
        return name
    return f"{name} {display}"


def _split_size_from_unit(unit: str) -> tuple[str | None, str]:
    parts = unit.strip().split()
    if len(parts) >= 2 and parts[0].lower() in _SIZE_WORDS:
        return parts[0], " ".join(parts[1:])
    return None, unit


def _format_amount_text(amount: IngredientAmount) -> str | None:
    qty = _amount_quantity(amount)
    if qty is None or qty <= 0:
        return None
    unit = _amount_unit(amount)
    if not unit:
        return _format_qty(qty)
    _size, unit_part = _split_size_from_unit(unit)
    canonical = _unit_key(unit_part)
    if canonical is None:
        return f"{_format_qty(qty)} {unit_part}"
    display = _display_unit(canonical, qty)
    return f"{_format_qty(qty)} {display}"


def _lemon_quantity_from_parsed(parsed: ParsedIngredient, original: str) -> float | None:
    text = _normalize_unicode(original.strip().lower())
    if _LEMON_LINE_RE.match(text):
        if parsed.amount:
            qty = _amount_quantity(parsed.amount[0])
            if qty is not None:
                return qty
        if "half" in text:
            return 0.5
    if parsed.name and parsed.name[0].text.lower() in {"lemon", "lemons"} and parsed.amount:
        return _amount_quantity(parsed.amount[0])
    return None


def _is_lemon_zest_ingredient(original: str, name: str = "") -> bool:
    stripped = original.strip()
    if _LEMON_LINE_RE.match(stripped) and re.search(r"\bzest\b", stripped, re.IGNORECASE):
        return True
    if re.search(r"\blemon\s+zest\b", stripped, re.IGNORECASE):
        return True
    return bool(name and re.search(r"\blemon\s+zest\b", name, re.IGNORECASE))


def _lemon_zest_quantity(original: str, parsed: ParsedIngredient) -> float:
    from_match = _FROM_LEMON_RE.search(original)
    if from_match:
        value = from_match.group(1).lower().strip()
        if value in {"half", "a half"}:
            return 0.5
        return _parse_qty(value)
    qty = _lemon_quantity_from_parsed(parsed, original)
    if qty is not None:
        return qty
    return 1.0


def _format_lemon_zest_storage(qty: float) -> str:
    if qty != 1:
        return f"zest {_format_qty(qty)} lemons"
    return "zest lemons"


def _canonicalize_grocery_name(name: str) -> str:
    lowered = name.lower().strip()
    if lowered in {"celery stalk", "celery stalks"}:
        return "celery"
    if re.match(r"^(?:\d+\s+)?(?:small|large|medium\s+)?celery\s+stalks?\Z", lowered):
        return "celery"
    return name


def _is_celery_stalk_unit(unit: str, name: str) -> bool:
    return "celery" in name.lower() and bool(re.search(r"stalks?", unit.lower()))


def _should_preserve_raw_line(line: str) -> bool:
    return bool(
        _SUBSTITUTION_PAREN_RE.search(line)
        or _TO_TASTE_RE.search(line)
        or line.strip().startswith(("[x]", "▢", "•", "*"))
    )


def _strip_trailing_prep_commas(text: str) -> str:
    changed = True
    while changed:
        changed = False
        updated = _PREP_TRAILING_RE.sub("", text).strip(" ,")
        if updated != text:
            text = updated
            changed = True
    return text


_DESCRIPTOR_WORDS = frozenset(
    {"curly", "tuscan", "loosely", "firmly", "ripe", "coarsely", "packed"}
)

_SIZE_WORDS = frozenset(
    {"large", "medium", "small", "extra-large", "extra", "jumbo", "baby", "thin", "thick"}
)

_DESCRIPTOR_COUNT_UNITS = frozenset(
    {"stalk", "stalks", "clove", "cloves", "can", "cans", "head", "heads", "bunch", "bunches"}
)


def _build_storage_line(
    parsed: ParsedIngredient,
    original: str,
    *,
    source_line: str | None = None,
) -> str:
    if not parsed.name:
        return _strip_trailing_prep_commas(original.strip())

    name = _simplify_parsed_name(parsed.name[0].text)
    name = _include_size_in_name(parsed, name)
    amounts = list(parsed.amount or [])
    selected = _select_amount(amounts, original)

    context = source_line or original
    if _is_lemon_zest_ingredient(context, name):
        return _format_lemon_zest_storage(_lemon_zest_quantity(context, parsed))

    if _LEMON_LINE_RE.match(original.strip()) or name == "lemons":
        if re.search(r"\bzest\b", original, re.IGNORECASE):
            lemon_qty = _lemon_quantity_from_parsed(parsed, original)
            if lemon_qty is not None and lemon_qty != 1:
                return f"zest {_format_qty(lemon_qty)} lemons"
            return "zest lemons"
        lemon_qty = _lemon_quantity_from_parsed(parsed, original)
        if lemon_qty is not None:
            return f"{_format_qty(lemon_qty)} lemons"
        if selected is not None:
            qty = _amount_quantity(selected)
            if qty is not None:
                return f"{_format_qty(qty)} lemons"
        return "lemons"

    if selected is None:
        return _prefer_plural_form(name)

    unit = _amount_unit(selected)
    _size, unit_part = _split_size_from_unit(unit)
    qty = _amount_quantity(selected)
    if qty is None:
        return _prefer_plural_form(name)

    if _is_celery_stalk_unit(unit_part, name):
        return f"{_format_qty(qty)} celery"

    if _is_volume_unit(unit_part):
        return name

    if _has_inline_oz_before_can(original):
        return _prefer_plural_form(name)

    unit_lower = unit_part.lower()
    if _is_weight_unit_strip_at_storage(unit_part):
        return _prefer_plural_form(name)

    if _is_garlic_clove_unit(unit_part, name):
        return f"clove:{_format_qty(qty)} garlic"

    if unit_lower in _DESCRIPTOR_COUNT_UNITS or unit_lower in {"stalk", "stalks"}:
        if "celery" in name.lower():
            return f"{_format_qty(qty)} celery".strip()
        return _format_with_descriptor_unit(qty, unit_part, name)

    amount_text = _format_amount_text(selected)
    if amount_text is None:
        return f"{_format_qty(qty)} {name}".strip()
    return f"{amount_text} {name}".strip()


def _parse_with_library(line: str) -> ParsedIngredient:
    _ensure_nltk_data()
    return parse_ingredient(line, string_units=True, separate_names=False)


def _strip_leading_to_prefix(text: str) -> str:
    return re.sub(r"^to\s+(?=\d)", "", text, flags=re.IGNORECASE).strip()


def format_ingredient_for_storage(line: str) -> str:
    """Parse a raw ingredient line into a cleaned ``{qty} {name}`` string for Notion."""
    from src.grocery_wizard.ingredients.normalize import is_junk_ingredient

    if is_junk_ingredient(line):
        return ""
    text = _strip_leading_to_prefix(
        _strip_or_prefix(_strip_optional_prefix(_normalize_unicode(line.strip())))
    )
    if not text:
        return ""
    if re.match(r"^(?:finely|freshly\s+grated\s+)?lemon\s+zest\Z", text, re.IGNORECASE):
        return "zest lemons"
    if _should_preserve_raw_line(line):
        return _strip_trailing_prep_commas(_normalize_unicode(line.strip()))
    parse_text = _strip_parenthetical_notes(text)
    parsed = _parse_with_library(parse_text)
    return _build_storage_line(parsed, parse_text, source_line=text)


def minimal_clean_for_storage(line: str) -> str:
    """Light cleanup for NYT Cooking lines that are already well-structured."""
    from src.grocery_wizard.ingredients.normalize import is_junk_ingredient

    text = _normalize_unicode(line.strip())
    if not text or is_junk_ingredient(text):
        return ""
    text = _strip_or_prefix(_strip_optional_prefix(text))
    text = _strip_prep_parenthetical_notes(text)
    text = _strip_trailing_prep_commas(text)
    return re.sub(r"\s+", " ", text).strip()


def ingredient_name(line: str) -> str:
    """Return the canonical grocery item name from a stored or raw ingredient line."""
    name, _ = parse_stored_ingredient(line)
    return name


def _strip_parenthetical_notes(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def _parse_stored_rest(qty_str: str, rest: str) -> tuple[str, str | None]:
    words = rest.split()
    if not words:
        return "", qty_str

    first = words[0].lower().rstrip(".,")
    if _is_volume_unit(first):
        name = " ".join(words[1:])
        return _prefer_plural_form(_strip_size_descriptors(_simplify_parsed_name(name))), None
    if len(words) == 1 and words[0].lower() == "garlic":
        return "garlic", None
    if qty_str and rest.strip().lower() == "garlic":
        return "garlic", None
    if _is_count_unit(first) or _unit_key(first) in {"lb", "oz", "g", "kg"}:
        unit = words[0]
        name = " ".join(words[1:])
        canonical = _unit_key(unit)
        if canonical in {"lb", "oz", "g", "kg"}:
            return _prefer_plural_form(_strip_size_descriptors(name)), f"{qty_str} {unit}"
        name = _prefer_plural_form(_strip_size_descriptors(name))
        return name, f"{qty_str} {unit}"

    name = _prefer_plural_form(_strip_size_descriptors(_simplify_parsed_name(rest)))
    if len(rest.split()) >= 2 and rest.split()[-1].lower() in {
        "stalks",
        "stalk",
        "cloves",
        "clove",
        "cans",
        "can",
    }:
        words = rest.split()
        unit_word = words[-1]
        base = " ".join(words[:-1])
        name = _prefer_plural_form(
            _strip_size_descriptors(_simplify_parsed_name(f"{base} {unit_word}"))
        )
    return _canonicalize_grocery_name(name), qty_str


_ZEST_LEMONS_RE = re.compile(
    r"^zest(?:\s+((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?))?\s+lemons?\Z",
    re.IGNORECASE,
)

_HEAD_GARLIC_RE = re.compile(
    r"^((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s+head(?:s)?\s+garlic\Z",
    re.IGNORECASE,
)

_STORED_CLOVE_GARLIC_RE = re.compile(
    r"^clove:((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s+garlic\Z",
    re.IGNORECASE,
)

_GARLIC_HEAD_LEGACY_RE = re.compile(
    r"^((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s+garlic\s+heads?\Z",
    re.IGNORECASE,
)

_GARLIC_CLOVE_HEAD_THRESHOLD = 10

_GARLIC_CLOVE_LINE_RE = re.compile(
    r"^((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s+"
    r"(?:(?:cloves?|clove)\s+(?:of\s+)?garlic|garlic\s+cloves?)\b",
    re.IGNORECASE,
)


def parse_stored_ingredient(line: str) -> tuple[str, str | None]:
    """Parse a cleaned ingredient line into ``(name, amount | None)``."""
    text = _normalize_unicode(line.strip())
    if not text:
        return "", None

    zest_match = _ZEST_LEMONS_RE.match(text)
    if zest_match:
        qty = zest_match.group(1).strip() if zest_match.group(1) else "1"
        return "lemons", f"zest:{qty}"

    head_garlic_match = _HEAD_GARLIC_RE.match(text) or _GARLIC_HEAD_LEGACY_RE.match(text)
    if head_garlic_match:
        return "garlic", f"head:{head_garlic_match.group(1).strip()}"

    stored_clove_match = _STORED_CLOVE_GARLIC_RE.match(text)
    if stored_clove_match:
        return "garlic", f"clove:{stored_clove_match.group(1).strip()}"

    if text.lower() == "garlic":
        return "garlic", None

    if _LEMON_ZEST_LEGACY_RE.match(text) or re.match(
        r"^(?:finely|freshly\s+grated\s+)?lemon\s+zest\Z", text, re.IGNORECASE
    ):
        return "lemons", "zest:1"

    match = _LEADING_QTY_RE.match(text)
    if match:
        qty_str = match.group(1).strip()
        rest = text[match.end() :].strip()
        if rest:
            return _parse_stored_rest(qty_str, rest)

    if looks_like_stored_ingredient_line(text):
        name = _prefer_plural_form(_strip_size_descriptors(_simplify_parsed_name(text)))
        return _canonicalize_grocery_name(name), None

    parsed = _parse_with_library(_strip_optional_prefix(text))
    name = _simplify_parsed_name(parsed.name[0].text) if parsed.name else text
    selected = _select_amount(list(parsed.amount or []), text)
    if selected is None or _is_volume_unit(_amount_unit(selected)):
        return _prefer_plural_form(name), None

    amount_text = _format_amount_text(selected)
    if amount_text is None:
        return _prefer_plural_form(name), None

    unit = _amount_unit(selected)
    qty = _amount_quantity(selected)
    if qty is not None and _is_garlic_clove_unit(unit, name):
        return "garlic", f"clove:{_format_qty(qty)}"
    if qty is not None and unit.lower() in _DESCRIPTOR_COUNT_UNITS:
        name = _append_unit_to_name(name, unit, qty)
        return _prefer_plural_form(name), _format_qty(qty)

    return _prefer_plural_form(name), amount_text


def _is_volume_measure_prefix(text: str) -> bool:
    match = _LEADING_QTY_RE.match(text)
    if not match:
        return False
    rest = text[match.end() :].strip()
    unit_match = re.match(r"^([a-zA-Z]+)", rest)
    if not unit_match:
        return False
    return _is_volume_unit(unit_match.group(1))


def looks_like_stored_ingredient_line(text: str) -> bool:
    stripped = text.strip()
    if re.match(r"^optional:", stripped, re.IGNORECASE):
        return False
    if re.match(r"^or\s+", stripped, re.IGNORECASE):
        return False
    if re.search(r"\d\s+or\s+\d", stripped):
        return False
    if re.search(r"\d(?:\s+\w+)+\s+or\s+\d", stripped):
        return False
    if re.search(r"\d+\s+to\s+\d+", stripped):
        return False
    if re.match(r"^\d+\s+\d+\s+", stripped):
        return False
    if _LEMON_ZEST_LEGACY_RE.match(stripped):
        return False
    if re.search(
        r"\b(?:packed|coarsely|finely|roughly|thinly)\s+(?:chopped|sliced|diced|minced)\b",
        stripped,
        re.IGNORECASE,
    ):
        return False
    if re.match(
        r"^(?:chopped|freshly ground|fresh|sliced|diced|minced|grated|"
        r"peeled|beaten|smashed|packed)\b",
        stripped,
        re.IGNORECASE,
    ):
        return False
    if _LEMON_LINE_RE.search(stripped):
        return False
    if re.search(
        r",\s*(?:minced|diced|chopped|grated|peeled|sliced|cut|smashed|drained|rinsed|beaten)\b",
        stripped,
        re.IGNORECASE,
    ):
        return False
    if re.search(r",.+\bor\b", stripped, re.IGNORECASE):
        return False
    if _TO_TASTE_RE.search(stripped):
        return False
    match = _LEADING_QTY_RE.match(stripped)
    if match:
        rest_words = stripped[match.end() :].strip().split()
        if rest_words and _is_volume_unit(rest_words[0]):
            return False
    return not ("(" in stripped and ")" in stripped)


def should_show_amount(amount: str | None, raw_line: str) -> bool:
    """Return whether a parsed amount should appear on the grocery list."""
    if amount is None:
        return False
    return _HIDE_AMOUNT_UNITS_RE.search(raw_line) is None


def _aggregate_lemon_amounts(amounts: list[str]) -> str:
    """Sum lemon counts, allowing one zest need to overlap with a whole lemon."""
    regular_total = 0.0
    zest_total = 0.0
    has_fractional = False
    for amount in amounts:
        if amount.startswith("zest:"):
            zest_total += _parse_qty(amount[5:])
            continue
        qty_str, _ = _split_amount_str(amount)
        qty = _parse_qty(qty_str)
        regular_total += qty
        if "/" in qty_str or qty % 1 != 0:
            has_fractional = True

    overlap = 0.0
    if zest_total > 0 and regular_total >= 2 and has_fractional:
        overlap = min(zest_total, 1.0)

    return str(math.ceil(regular_total + zest_total - overlap))


def _aggregate_garlic_amounts(amounts: list[str | None]) -> str | None:
    """Combine garlic needs: sum explicit heads, convert cloves to implied heads."""
    head_total = 0.0
    clove_total = 0.0
    has_bare_garlic = False

    for amount in amounts:
        if amount is None:
            has_bare_garlic = True
            continue
        if amount.startswith("head:"):
            head_total += _parse_qty(amount[5:])
            continue
        if amount.startswith("clove:"):
            clove_total += _parse_qty(amount[6:])
            continue
        try:
            _parse_qty(amount)
        except (ValueError, ZeroDivisionError):
            has_bare_garlic = True

    if clove_total > _GARLIC_CLOVE_HEAD_THRESHOLD:
        clove_heads = 2.0
    else:
        clove_heads = 0.0

    total_heads = max(head_total, clove_heads)
    if total_heads > 0:
        return _format_qty(total_heads)
    if has_bare_garlic or clove_total > 0:
        return None
    return None


def aggregate_amounts(amounts: list[str | None], *, name: str | None = None) -> str | None:
    """Aggregate amount strings by summing matched units."""
    non_none = [amount for amount in amounts if amount is not None]
    if not non_none and not amounts:
        return None
    if name and name.lower() == "garlic":
        return _aggregate_garlic_amounts(amounts)
    if not non_none:
        return None
    if len(non_none) == 1:
        return non_none[0]

    if any(amount.startswith("zest:") for amount in non_none):
        return _aggregate_lemon_amounts(non_none)

    parsed = [_split_amount_str(amount) for amount in non_none]
    canon_units = {_canonical_unit(unit) for _, unit in parsed}

    if len(canon_units) != 1:
        return non_none[0]

    canonical = next(iter(canon_units))
    try:
        total = sum(_parse_qty(qty_str) for qty_str, _ in parsed)
    except (ValueError, ZeroDivisionError):
        return non_none[0]

    qty_formatted = _format_qty(total)
    if canonical is None:
        return str(math.ceil(total))

    orig_unit = parsed[0][1]
    singular, plural = _UNIT_DISPLAY.get(canonical, (orig_unit, f"{orig_unit}s"))
    display_unit = plural if total > 1 else singular
    return f"{qty_formatted} {display_unit}"


def _split_amount_str(amount: str) -> tuple[str, str | None]:
    match = _AMOUNT_STR_RE.match(amount.strip())
    if match is None:
        return (amount, None)
    qty_str = match.group(1).strip()
    unit_part = match.group(2).strip() if match.group(2) else None
    return (qty_str, unit_part or None)


def _canonical_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    return _UNIT_CANONICAL.get(unit.lower(), unit.lower())


normalize_ingredient = ingredient_name
parse_amount = parse_stored_ingredient
clean_ingredient_line_for_storage = format_ingredient_for_storage
