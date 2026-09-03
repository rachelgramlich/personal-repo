"""Rule-based ingredient normalization for grocery lists."""

from __future__ import annotations

import re

# Leading quantity: integers, fractions, mixed numbers, ranges.
_QUANTITY_RE = re.compile(
    r"^[\d\s./-]+|" r"^(?:a|an)\s+",
    re.IGNORECASE,
)

# Captures a leading numeric quantity (integer, decimal, fraction, or mixed
# number like "2 1/2") at the start of a string.
_LEADING_QTY_RE = re.compile(
    r"^((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s*",
)

# Same pattern but also captures any trailing text (unit / rest).
_AMOUNT_STR_RE = re.compile(
    r"^((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s*(.*)\Z",
    re.DOTALL,
)

_UNICODE_DASHES = ("–", "—", "−")  # en-dash, em-dash, minus sign

_UNITS = {
    "teaspoon",
    "teaspoons",
    "tsp",
    "tablespoon",
    "tablespoons",
    "tbsp",
    "cup",
    "cups",
    "ounce",
    "ounces",
    "oz",
    "pound",
    "pounds",
    "lb",
    "lbs",
    "gram",
    "grams",
    "g",
    "kilogram",
    "kilograms",
    "kg",
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
}

_SIZES = {
    "large",
    "medium",
    "small",
    "extra-large",
    "extra large",
    "xl",
    "jumbo",
    "baby",
    "thin",
    "thick",
}

_PREP_PHRASES = (
    "freshly ground",
    "at room temperature",
    "lightly packed",
    "firmly packed",
    "cut into wedges",
)

_PREP_WORDS = {
    "beaten",
    "chopped",
    "diced",
    "minced",
    "sliced",
    "grated",
    "shredded",
    "crushed",
    "peeled",
    "seeded",
    "cored",
    "trimmed",
    "halved",
    "quartered",
    "julienned",
    "cubed",
    "mashed",
    "softened",
    "melted",
    "room temperature",
    "at room temperature",
    "freshly ground",
    "fresh",
    "dried",
    "frozen",
    "thawed",
    "cooked",
    "raw",
    "boneless",
    "skinless",
    "bone-in",
    "skin-on",
    "whole",
    "divided",
    "packed",
    "lightly packed",
    "firmly packed",
    "finely",
    "coarsely",
    "roughly",
    "thinly",
    "thickly",
    "rinsed",
    "drained",
    "optional",
    "wedges",
}

# Prep descriptors stripped from the start of an ingredient name.
_STRIP_LEADING_PREP = {
    "beaten",
    "chopped",
    "fresh",
    "minced",
    "peeled",
    "seeded",
    "cored",
    "trimmed",
    "halved",
    "quartered",
    "julienned",
    "cubed",
    "mashed",
    "softened",
    "melted",
    "thawed",
    "rinsed",
    "drained",
    "finely",
    "coarsely",
    "roughly",
    "thinly",
    "thickly",
    "optional",
}

_JUNK_ONLY_PHRASES = frozenset(
    {
        "rinsed",
        "drained",
        "rinsed and drained",
        "drained and rinsed",
        "divided",
        "optional",
        "for garnish",
        "to serve",
        "to taste",
        "as needed",
        "if needed",
        "for serving",
        "for topping",
    }
)

_TRAILING_CLAUSE_RE = re.compile(
    r"\b(?:plus more for|such as|or to taste|to taste|for garnish|optional|"
    r"as needed|if needed|for serving|for topping|to serve)\b.*",
    re.IGNORECASE,
)

_CONJUNCTION_SPLIT_RE = re.compile(r"\s+(?:and|&)\s+", re.IGNORECASE)

# Compound phrases that should stay together despite containing "and" or "&".
_UNSPLIT_AND_PHRASES = frozenset(
    {
        "salt and pepper",
        "salt & pepper",
        "mac and cheese",
        "fish and chips",
        "bread and butter",
        "peanut butter and jelly",
        "cookies and cream",
        "oil and vinegar",
        "ham and cheese",
        "gin and tonic",
        "rice and beans",
    }
)

# Singular -> preferred grocery-store plural form.
_PLURALS: dict[str, str] = {
    "egg": "eggs",
    "tomato": "tomatoes",
    "potato": "potatoes",
    "onion": "onions",
    "carrot": "carrots",
    "mushroom": "mushrooms",
    "clove": "garlic",
    "lemon": "lemons",
    "lime": "limes",
    "apple": "apples",
    "banana": "bananas",
    "avocado": "avocados",
    "scallion": "scallions",
    "shallot": "shallots",
}


def _normalize_unicode_dashes(text: str) -> str:
    for dash in _UNICODE_DASHES:
        text = text.replace(dash, "-")
    return text


def expand_ingredient_line(line: str) -> list[str]:
    """Split compound ingredient lines into separate grocery items."""
    text = _normalize_unicode_dashes(line.strip())
    if not text:
        return []
    return _split_compound_parts(text)


def split_compound_ingredients(text: str) -> list[str]:
    """Expand compound ingredient lines in multiline text to one item per line."""
    if not text or not text.strip():
        return []

    expanded: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        expanded.extend(expand_ingredient_line(line))
    return expanded


def _split_compound_parts(text: str) -> list[str]:
    split = _try_split_on_conjunction(text)
    if split is None:
        return [text]
    left, right = split
    return _split_compound_parts(left) + _split_compound_parts(right)


def _try_split_on_conjunction(text: str) -> tuple[str, str] | None:
    main = re.sub(r"\([^)]*\)", "", text).split(",")[0].strip()
    main = _TRAILING_CLAUSE_RE.sub("", main).strip().lower()
    if main in _UNSPLIT_AND_PHRASES:
        return None

    match = _CONJUNCTION_SPLIT_RE.search(text)
    if match is None:
        return None

    left = text[: match.start()].strip().rstrip(",")
    right = text[match.end() :].strip()
    if not left or not right:
        return None
    if not _looks_like_ingredient(left) or not _looks_like_ingredient(right):
        return None
    return left, right


def _looks_like_ingredient(part: str) -> bool:
    cleaned = re.sub(r"\([^)]*\)", "", part).strip()
    cleaned = cleaned.split(",")[0].strip()
    cleaned = _TRAILING_CLAUSE_RE.sub("", cleaned).strip()
    if not cleaned:
        return False

    words = cleaned.lower().split()
    words = _strip_leading_tokens(words, _UNITS | _SIZES)
    while words and words[0] in _PREP_WORDS:
        words.pop(0)
    if not words:
        return False
    if len(words) >= 2:
        return True
    return len(words[0]) >= 4


def is_junk_ingredient(line: str) -> bool:
    """Return True when a line is only prep instructions, not a grocery item."""
    return _is_junk_only(line)


def normalize_ingredient(line: str) -> str:
    """Reduce a recipe ingredient line to a grocery-store item name."""
    text = _normalize_unicode_dashes(line.strip().lower())
    if not text:
        return ""

    if _is_junk_only(text):
        return ""

    text = re.sub(r"\([^)]*\)", "", text)
    text = text.split(",")[0]
    text = _TRAILING_CLAUSE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()

    text = _QUANTITY_RE.sub("", text).strip()
    words = text.split()
    words = _strip_leading_tokens(words, _UNITS | _SIZES)
    text = " ".join(words).strip()

    text = _strip_trailing_prep(text)
    text = _strip_leading_prep(text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return ""

    return _prefer_plural_form(text)


def _strip_leading_tokens(words: list[str], skip: set[str]) -> list[str]:
    while words:
        token = words[0].rstrip(".")
        if token in skip:
            words.pop(0)
            continue
        break
    return words


def _strip_trailing_prep(text: str) -> str:
    lowered = text.lower()
    changed = True
    while changed:
        changed = False
        for prep in sorted(_PREP_WORDS, key=len, reverse=True):
            if lowered == prep:
                return ""
            suffix = f", {prep}"
            if lowered.endswith(suffix):
                text = text[: -len(suffix)]
                lowered = text.lower()
                changed = True
                break
            if lowered.endswith(f" {prep}"):
                text = text[: -len(prep)].rstrip()
                lowered = text.lower()
                changed = True
                break
    return text.strip(" ,")


def _strip_leading_prep(text: str) -> str:
    lowered = text.lower()
    changed = True
    while changed:
        changed = False
        for phrase in sorted(_PREP_PHRASES, key=len, reverse=True):
            if lowered.startswith(f"{phrase} "):
                text = text[len(phrase) + 1 :]
                lowered = text.lower()
                changed = True
                break
        if changed:
            continue
        words = text.split()
        if words and words[0].rstrip(".,") in _STRIP_LEADING_PREP:
            text = " ".join(words[1:])
            lowered = text.lower()
            changed = True
    return text.strip()


def _is_junk_only(text: str) -> bool:
    cleaned = text.strip().lower()
    if not cleaned:
        return True

    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    cleaned = cleaned.split(",")[0]
    cleaned = _TRAILING_CLAUSE_RE.sub("", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return True
    if cleaned in _JUNK_ONLY_PHRASES:
        return True

    for part in _CONJUNCTION_SPLIT_RE.split(cleaned):
        part = part.strip()
        if not part:
            continue
        part = _QUANTITY_RE.sub("", part).strip()
        words = part.split()
        words = _strip_leading_tokens(words, _UNITS | _SIZES)
        while words and words[0].rstrip(".,") in _PREP_WORDS:
            words.pop(0)
        if words:
            return False
    return True


def _prefer_plural_form(text: str) -> str:
    """Normalize common singulars to grocery-friendly names."""
    words = text.split()
    if not words:
        return text

    last = words[-1]
    if last in _PLURALS:
        words[-1] = _PLURALS[last]
        return " ".join(words)

    if last == "garlic" and len(words) > 1 and words[0] in {"clove", "cloves"}:
        return "garlic"

    return text


# ---------------------------------------------------------------------------
# Amount parsing and aggregation
# ---------------------------------------------------------------------------

# Maps any recognised unit spelling to a canonical comparison key.
_UNIT_CANONICAL: dict[str, str] = {
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsp": "tsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsp": "tbsp",
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
}

# Maps canonical key -> (singular_display, plural_display).
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
}


def parse_amount(line: str) -> tuple[str, str | None]:
    """Parse a raw ingredient line into ``(normalized_name, amount_str | None)``.

    The amount string (e.g. ``"1 lb"``, ``"2 cans"``, ``"3 cloves"``) is
    ready for display.  Returns ``None`` for the amount when no leading
    numeric quantity is present or when the bare count is exactly 1 (showing
    ``"1 onions"`` is less useful than just ``"onions"``).

    Examples::

        parse_amount("1 lb chicken breast") == ("chicken breast", "1 lb")
        parse_amount("2 cans white beans")  == ("white beans", "2 cans")
        parse_amount("3 cloves garlic")     == ("garlic", "3 cloves")
        parse_amount("2 eggs")              == ("eggs", "2")
        parse_amount("kosher salt")         == ("kosher salt", None)
    """
    normalized = normalize_ingredient(line)
    if not normalized:
        return normalized, None

    text = _normalize_unicode_dashes(line.strip().lower())
    m = _LEADING_QTY_RE.match(text)
    if m is None:
        return normalized, None

    qty_str = m.group(1).strip()
    rest = text[m.end() :].strip()

    # Skip an inline descriptor like "(15-ounce)" that may follow the number.
    rest = re.sub(r"^\([^)]*\)\s*", "", rest)

    # Check whether a recognised unit word comes next.
    unit_match = re.match(r"^([a-zA-Z]+\.?)\b", rest)
    if unit_match:
        candidate = unit_match.group(1).rstrip(".")
        if candidate in _UNITS:
            return normalized, f"{qty_str} {candidate}"

    # No recognised unit — only return a bare count when quantity > 1.
    # Showing "1 onions" is worse than just "onions".
    try:
        if _parse_qty(qty_str) > 1:
            return normalized, qty_str
    except (ValueError, ZeroDivisionError):
        pass
    return normalized, None


def aggregate_amounts(amounts: list[str | None]) -> str | None:
    """Aggregate a list of amount strings by summing matched units.

    When all non-``None`` amounts share the same canonical unit the quantities
    are summed and returned as a formatted string.  When units differ, or
    parsing fails, the first non-``None`` amount is returned unchanged.
    Returns ``None`` when there are no amounts.

    Examples::

        aggregate_amounts(["1 can", "1 can"]) == "2 cans"
        aggregate_amounts(["1 lb", "500g"])   == "1 lb"
        aggregate_amounts([None, None])        == None
    """
    non_none = [a for a in amounts if a is not None]
    if not non_none:
        return None
    if len(non_none) == 1:
        return non_none[0]

    parsed = [_split_amount_str(a) for a in non_none]
    canon_units = {_canonical_unit(unit) for _, unit in parsed}

    if len(canon_units) != 1:
        # Mixed units — return first amount unchanged.
        return non_none[0]

    canonical = next(iter(canon_units))
    try:
        total = sum(_parse_qty(qty_str) for qty_str, _ in parsed)
    except (ValueError, ZeroDivisionError):
        return non_none[0]

    qty_formatted = _format_qty(total)
    if canonical is None:
        # Bare counts (no unit).
        return qty_formatted

    orig_unit = parsed[0][1]  # e.g. "can" or "cans" from the first amount
    singular, plural = _UNIT_DISPLAY.get(canonical, (orig_unit, orig_unit + "s"))
    display_unit = plural if total > 1 else singular
    return f"{qty_formatted} {display_unit}"


# --- Private helpers for amount parsing/aggregation ---


def _split_amount_str(amount: str) -> tuple[str, str | None]:
    """Split ``"2 cans"`` → ``("2", "cans")``; ``"3"`` → ``("3", None)``.

    Handles mixed-number quantities like ``"2 1/2 cups"`` → ``("2 1/2", "cups")``.
    """
    m = _AMOUNT_STR_RE.match(amount.strip())
    if m is None:
        return (amount, None)
    qty_str = m.group(1).strip()
    unit_part = m.group(2).strip() if m.group(2) else None
    return (qty_str, unit_part if unit_part else None)


def _canonical_unit(unit: str | None) -> str | None:
    """Return canonical unit key for comparison, or ``None``."""
    if unit is None:
        return None
    return _UNIT_CANONICAL.get(unit.lower(), unit.lower())


def _parse_qty(s: str) -> float:
    """Parse a quantity string: ``"1/2"`` → 0.5, ``"2 1/2"`` → 2.5."""
    s = s.strip()
    if " " in s:
        whole, frac = s.split(None, 1)
        return float(whole) + _parse_qty(frac)
    if "/" in s:
        num, denom = s.split("/", 1)
        return float(num) / float(denom)
    return float(s)


def _format_qty(qty: float) -> str:
    """Format a quantity as a clean string (whole number, simple fraction, or decimal)."""
    if qty == int(qty):
        return str(int(qty))
    whole = int(qty)
    frac = qty - whole
    for num, denom in ((1, 4), (1, 3), (1, 2), (2, 3), (3, 4)):
        if abs(frac - num / denom) < 0.005:
            if whole:
                return f"{whole} {num}/{denom}"
            return f"{num}/{denom}"
    # Fall back to decimal, stripping trailing zeros.
    return f"{qty:.2f}".rstrip("0").rstrip(".")
