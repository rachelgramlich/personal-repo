"""Rule-based ingredient normalization for grocery lists."""

from __future__ import annotations

import re

# Leading quantity: integers, fractions, mixed numbers, ranges.
_QUANTITY_RE = re.compile(
    r"^[\d\s./-]+|" r"^(?:a|an)\s+",
    re.IGNORECASE,
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
