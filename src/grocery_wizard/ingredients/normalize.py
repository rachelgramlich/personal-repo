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
        "more as needed",
        "if needed",
        "for serving",
        "for topping",
    }
)

_DESCRIPTOR_WORDS = frozenset(
    {
        "curly",
        "tuscan",
        "loosely",
        "firmly",
        "ripe",
    }
)

_HIDE_AMOUNT_UNITS_RE = re.compile(
    r"\b(tsp|teaspoons?|tbsp|tablespoons?|cups?|packed|ounces?|oz)\b",
    re.IGNORECASE,
)

# Prep words that can appear as alternatives: "minced or grated".
_PREP_ALTERNATIVE_RE = re.compile(
    r"^(?:"
    + "|".join(re.escape(word) for word in sorted(_PREP_WORDS, key=len, reverse=True))
    + r")"
    r"(?:\s+or\s+(?:"
    + "|".join(re.escape(word) for word in sorted(_PREP_WORDS, key=len, reverse=True))
    + r"))+$",
    re.IGNORECASE,
)

_GROUND_MEATS = frozenset({"beef", "turkey", "pork", "chicken", "lamb", "veal", "sausage", "bison"})

_TOMATO_PREP_FORMS = frozenset(
    {"diced", "crushed", "stewed", "fire-roasted", "whole", "whole peeled"}
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

_TRAILING_CLAUSE_RE = re.compile(
    r"\b(?:plus more for|plus more\b|such as|or to taste|to taste|for garnish|optional|"
    r"as needed|if needed|for serving|for topping|to serve)\b.*",
    re.IGNORECASE,
)

_TRAILING_MORE_RE = re.compile(r"\s+more$", re.IGNORECASE)

_LEADING_TO_PREFIX_RE = re.compile(r"^to\s+(?=\d)", re.IGNORECASE)

_QTY_RANGE_RE = re.compile(
    r"^((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)(?:\s+(?:large|medium|small))?\s+or\s+"
    r"((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)(?:\s+(?:large|medium|small))?\s+",
    re.IGNORECASE,
)

_QTY_TO_RANGE_RE = re.compile(
    r"^((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s+to\s+" r"((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s+",
    re.IGNORECASE,
)

_LEMON_VARIANT_RE = re.compile(
    r"^(?:"
    r"(?:juice|zest|grated zest) of (?:half(?:\s+a)?|(?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s+lemons?|"
    r"lemons? (?:juice|zest)"
    r")$",
    re.IGNORECASE,
)

# Cut/trim instructions after the ingredient name (not product descriptors).
_TRAILING_CUT_INSTRUCTION_RE = re.compile(
    r",?\s+(?:"
    r"cut\s+into\s+(?:\d+[- ]inch\s+)?(?:pieces?|strips?|chunks?|cubes?|wedges?)|"
    r"trimmed(?:\s+(?:and\s+)?(?:thinly|thickly|finely))?\s+"
    r"(?:sliced|cut|diced|chopped|minced|julienned)(?:\s+on\s+an\s+angle)?|"
    r"(?:thinly|thickly|finely|roughly)\s+"
    r"(?:sliced|cut|diced|chopped|minced|julienned)(?:\s+on\s+an\s+angle)?|"
    r"(?:sliced|diced|chopped|minced|julienned|halved|quartered|peeled|seeded)"
    r"(?:\s+into)?(?:\s+(?:\d+[- ]inch\s+)?pieces?)?|"
    r"sliced\s+\d+(?:/\d+)?\s*inch\s+(?:thick|thin)\s+(?:lengthwise|crosswise)"
    r")\s*$",
    re.IGNORECASE,
)

_INCOMPLETE_PREP_SUFFIX_RE = re.compile(
    r"\b(?:peeled|rolled|drained|rinsed|smashed|halved|trimmed|seeded|grated|"
    r"chopped|diced|minced|sliced|julienned|cubed|mashed)\s+and\s*$",
    re.IGNORECASE,
)

_HERB_LEAVES_RE = re.compile(
    r"^(?:(?:fresh|chopped|loosely|firmly)\s+)*(?:packed\s+)?"
    r"(cilantro|basil|parsley|mint|dill|thyme|oregano|sage|rosemary|celery)\s+leaves$",
    re.IGNORECASE,
)

_CELERY_LEAVES_RE = re.compile(
    r"^(?:(?:\d+(?:\s+\d+/\d+)?|\d+/\d+|\d+(?:\.\d+)?)\s+)?"
    r"(?:(?:cups?|tablespoons?|tbsp|teaspoons?|tsp|ounces?|oz)\s+)?"
    r"(?:(?:loosely|firmly)\s+)?(?:packed\s+)?celery\s+leaves$",
    re.IGNORECASE,
)

# Known grocery nouns for splitting recipe-title bleed (no qty/unit on the line).
_GROCERY_NOUNS = frozenset(
    {
        "asparagus",
        "basil",
        "beans",
        "beef",
        "bread",
        "broccoli",
        "carrots",
        "celery",
        "cheese",
        "chicken",
        "chickpeas",
        "chimichurri",
        "cilantro",
        "corn",
        "cucumber",
        "eggs",
        "feta",
        "fish",
        "garlic",
        "ginger",
        "gnocchi",
        "gochujang",
        "kale",
        "kimchi",
        "leeks",
        "lemon",
        "lemons",
        "lime",
        "limes",
        "mushrooms",
        "onion",
        "onions",
        "orzo",
        "parsley",
        "pasta",
        "pepper",
        "potatoes",
        "rice",
        "salmon",
        "scallions",
        "shrimp",
        "spinach",
        "tofu",
        "tomatoes",
        "tortellini",
        "tuna",
        "turkey",
        "veggie",
        "zucchini",
    }
)

_RECIPE_TITLE_FILLER = frozenset({"sauce", "with", "w", "and", "for"})

# Standalone prep/cut instructions (often scraped as their own line).
_INSTRUCTION_ONLY_RE = re.compile(
    r"^(?:(?:thinly|thickly|roughly|finely|lightly)\s+)?"
    r"(?:sliced|cut|diced|chopped|minced|halved|quartered|julienned|cubed|trimmed|peeled|seeded)"
    r"(?:\s+into)?"
    r"(?:\s+"
    r"(?:half[- ]moons?|wedges?|strips?|rounds?|cubes?|chunks?|pieces?|"
    r"bite[- ]size(?:\s+pieces?)?|\d+[- ]inch(?:\s+pieces?)?|small\s+pieces?|"
    r"thin\s+slices?|thick\s+slices?)"
    r")?"
    r"\s*$",
    re.IGNORECASE,
)

# Comma-separated prep with dimensions: ``sliced 1/4 inch thick lengthwise``.
_DIMENSION_PREP_SEGMENT_RE = re.compile(
    r"^(?:(?:thinly|thickly|finely|roughly)\s+)?"
    r"(?:sliced|cut|diced|chopped|minced|julienned|halved|quartered|peeled|seeded|trimmed|grated|shredded|crushed)"
    r"(?:\s+(?:\d+(?:/\d+)?\s*)?(?:-| )?(?:inch|inches|in|cm|mm))?"
    r"(?:\s+(?:thick|thin|lengthwise|crosswise|diagonally|wide|long))+"
    r"\s*$",
    re.IGNORECASE,
)

_CONJUNCTION_SPLIT_RE = re.compile(r"\s+(?:and|&)\s+", re.IGNORECASE)

# Recipe-step lines and cooking instructions (not grocery items).
_RECIPE_STEP_RE = re.compile(r"^\d+\.(?:\s|\t)")
_CHECKLIST_ITEM_RE = re.compile(r"^\d+\.\s*(?:\[\s*\]\s*)")
_INSTRUCTION_VERB_RE = re.compile(
    r"^(?:combine|meanwhile|when ready|for a |clean and|grill|cut |spoon|serve|"
    r"transfer|brush|arrange|heat |reduce |bring |pat |whisk |cover|open |add |stir|"
    r"taste|season|let |simmer|dissolve|return|remove|place|preheat|bake|roast|"
    r"cook|mix|fold|pour|drain|rinse|slice|chop|dice|mince|grate|peel|mash)\b",
    re.IGNORECASE,
)
_METADATA_LINE_RE = re.compile(
    r"^(?:recipe\s+)?serves?\s+\d+|^serves?\s+\d+|yield:?\s+\d+|makes?\s+\d+",
    re.IGNORECASE,
)
# Split merged scrape artifacts: ``Russets2 Tablespoons`` or ``pepper1/4 cup``.
_MERGED_QTY_SPLIT_RE = re.compile(
    r"(?<=[A-Za-z)\]])"
    r"(?=(?:\d+(?:\s+\d+/\d+)?|\d+/\d+|\d+(?:\.\d+)?)(?:\s*-\s*\d+)?\s*"
    r"(?:pounds?|tablespoons?|tbsp|teaspoons?|tsp|cups?|ounces?|oz|grams?|g|"
    r"milliliters?|ml|liters?|l|cloves?|cans?|bunch(?:es)?|heads?|sticks?|"
    r"packages?|pkg|pinch(?:es)?|dash(?:es)?)\b)",
    re.IGNORECASE,
)
_MERGED_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")

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
    for char, replacement in _UNICODE_FRACTIONS.items():
        text = text.replace(char, replacement)
    return text


def _normalize_unicode_fractions(text: str) -> str:
    for char, replacement in _UNICODE_FRACTIONS.items():
        text = text.replace(char, replacement)
    return text


def expand_ingredient_line(line: str) -> list[str]:
    """Split compound ingredient lines into separate grocery items."""
    text = _normalize_unicode_fractions(_normalize_unicode_dashes(line.strip()))
    if not text:
        return []

    title_bleed = split_recipe_title_bleed(text)
    if len(title_bleed) > 1:
        expanded: list[str] = []
        for part in title_bleed:
            expanded.extend(_split_compound_parts_recursive(part))
        return expanded

    return _split_compound_parts_recursive(text)


def split_recipe_title_bleed(text: str) -> list[str]:
    """Split concatenated recipe-title artifacts into separate grocery items."""
    stripped = text.strip()
    if not stripped or re.match(r"^[\d¼½¾⅓⅔⅛⅜⅝⅞]", stripped):
        return [text]

    # Real compound ingredients use conjunctions; title bleed does not.
    if _CONJUNCTION_SPLIT_RE.search(stripped):
        return [text]

    # ``gnocchi sauce veggie for gnocchi`` → ``gnocchi``, ``veggie for gnocchi``
    repeat_match = re.match(
        r"^(\w+)\s+(?:\w+\s+)*(\w+)\s+for\s+\1\s*$",
        stripped,
        re.IGNORECASE,
    )
    if repeat_match:
        noun = repeat_match.group(1)
        middle = repeat_match.group(2)
        return [noun, f"{middle} for {noun}"]

    words = stripped.lower().split()
    if len(words) < 2:
        return [text]

    if any(word in _UNITS for word in words):
        return [text]

    # Only split when every token is a known noun or title filler — avoids
    # breaking ``sesame oil gochujang kimchi`` or ``chopped fresh cilantro``.
    if not all(word in _GROCERY_NOUNS or word in _RECIPE_TITLE_FILLER for word in words):
        return [text]

    noun_positions = [index for index, word in enumerate(words) if word in _GROCERY_NOUNS]
    if len(noun_positions) < 2:
        return [text]

    parts: list[str] = []
    start = 0
    for position in noun_positions:
        chunk_words = words[start : position + 1]
        while chunk_words and chunk_words[0] in _RECIPE_TITLE_FILLER:
            chunk_words.pop(0)
        if chunk_words:
            parts.append(" ".join(chunk_words))
        start = position + 1

    if start < len(words):
        trailing = [word for word in words[start:] if word not in _RECIPE_TITLE_FILLER]
        if trailing:
            parts.append(" ".join(trailing))

    if len(parts) < 2:
        return [text]

    return parts


def _split_compound_parts_recursive(text: str) -> list[str]:
    split = _try_split_on_conjunction(text)
    if split is None:
        return [text]
    left, right = split
    return _split_compound_parts_recursive(left) + _split_compound_parts_recursive(right)


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
    return _split_compound_parts_recursive(text)


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
    from src.grocery_wizard.ingredients.parsed import _strip_optional_prefix

    return _is_junk_only(_strip_optional_prefix(line.strip()))


def drop_junk_ingredient_lines(lines: list[str]) -> list[str]:
    """Remove prep-only instruction lines from scraped ingredient lists."""
    return [line for line in lines if line.strip() and not is_junk_ingredient(line)]


def is_metadata_line(line: str) -> bool:
    """Return True for yield/serves headers, not grocery items."""
    return bool(_METADATA_LINE_RE.match(line.strip()))


def is_instruction_line(line: str) -> bool:
    """Return True when a line is a cooking step, not a grocery item."""
    stripped = line.strip()
    if not stripped:
        return True
    if _RECIPE_STEP_RE.match(stripped):
        return True
    if is_metadata_line(stripped):
        return True
    if _INSTRUCTION_VERB_RE.match(stripped):
        return True
    if _INSTRUCTION_ONLY_RE.match(stripped):
        return True
    if len(stripped) > 100 and _INSTRUCTION_VERB_RE.search(stripped):
        return True
    return False


def is_recipe_step_line(line: str) -> bool:
    """Return True for numbered recipe steps (truncate remaining lines after)."""
    stripped = line.strip()
    if _CHECKLIST_ITEM_RE.match(stripped):
        return False
    return bool(_RECIPE_STEP_RE.match(stripped))


def split_merged_ingredient_line(line: str) -> list[str]:
    """Split scrape artifacts where multiple ingredients were joined on one line."""
    text = _normalize_unicode_dashes(line.strip())
    if not text:
        return []

    parts: list[str] = []
    for segment in _MERGED_CAMEL_SPLIT_RE.split(text):
        segment = segment.strip()
        if not segment:
            continue
        for piece in _MERGED_QTY_SPLIT_RE.split(segment):
            piece = piece.strip()
            if not piece:
                continue
            parts.extend(_split_leading_capitalized_ingredient(piece))
    return parts or [text]


def _split_leading_capitalized_ingredient(piece: str) -> list[str]:
    """``Salt fresh black pepper`` → ``Salt`` + ``fresh black pepper``."""
    words = piece.split(None, 1)
    if len(words) != 2:
        return [piece]
    first, rest = words
    if first[0].isupper() and rest[0].islower() and first.lower() in _STANDALONE_INGREDIENT_WORDS:
        return [first, rest]
    return [piece]


_STANDALONE_INGREDIENT_WORDS = frozenset(
    {
        "salt",
        "pepper",
        "sugar",
        "flour",
        "butter",
        "eggs",
        "milk",
        "water",
        "oil",
    }
)


_STORAGE_KEEP_SEGMENTS = frozenset(
    {
        "to taste",
        "more to taste",
        "optional",
        "for garnish",
        "to serve",
        "as needed",
        "if needed",
        "for serving",
        "for topping",
    }
)


def _strip_leading_amount(text: str) -> str:
    """Remove leading quantities, including dual measures like ``1 cup/110 grams``."""
    text = re.sub(r"^\d+\s+\w+/\d+\s+\w+\s+", "", text, flags=re.IGNORECASE)
    return _QUANTITY_RE.sub("", text).strip()


def _strip_leading_tokens(words: list[str], skip: set[str]) -> list[str]:
    while words:
        token = words[0].rstrip(".")
        if token in skip:
            words.pop(0)
            continue
        break
    return words


def _is_prep_alternative_phrase(text: str) -> bool:
    return bool(_PREP_ALTERNATIVE_RE.match(text.strip()))


def _strip_prep_words(words: list[str]) -> list[str]:
    while words:
        token = words[0].rstrip(".,")
        if token == "and" and len(words) > 1 and words[1].rstrip(".,") in _PREP_WORDS:
            words.pop(0)
            continue
        if token in _PREP_WORDS:
            words.pop(0)
            continue
        break
    return words


def _is_prep_only_segment(segment: str) -> bool:
    segment = _TRAILING_CLAUSE_RE.sub("", segment).strip()
    if not segment:
        return True
    if segment in _JUNK_ONLY_PHRASES or segment == "more":
        return True
    if _INSTRUCTION_ONLY_RE.match(segment):
        return True
    if _DIMENSION_PREP_SEGMENT_RE.match(segment):
        return True
    if _is_prep_alternative_phrase(segment):
        return True

    segment = _strip_leading_amount(segment)
    words = segment.split()
    words = _strip_leading_tokens(words, _UNITS | _SIZES)
    words = _strip_prep_words(words)
    return not words


def _is_junk_only(text: str) -> bool:
    cleaned = text.strip().lower()
    if not cleaned:
        return True

    without_parens = re.sub(r"\([^)]*\)", "", cleaned).strip()
    if _INSTRUCTION_ONLY_RE.match(without_parens):
        return True

    segments = [segment.strip() for segment in without_parens.split(",") if segment.strip()]
    if not segments:
        return True

    return all(_is_prep_only_segment(segment) for segment in segments)


from src.grocery_wizard.ingredients.parsed import (  # noqa: E402, F401
    _format_qty,
    aggregate_amounts,
    format_ingredient_for_storage,
    garlic_clove_count_from_line,
    is_nyt_cooking_url,
    looks_like_stored_ingredient_line,
    minimal_clean_for_storage,
    should_show_amount,
)
from src.grocery_wizard.ingredients.parsed import (  # noqa: E402
    parse_stored_ingredient as _parse_stored_ingredient,
)


def clean_ingredient_line_for_storage(line: str) -> str:
    return format_ingredient_for_storage(line)


def _prepare_line_for_parsing(line: str) -> str:
    from src.grocery_wizard.ingredients.parsed import (
        _normalize_unicode,
        _strip_leading_to_prefix,
        _strip_optional_prefix,
        _strip_or_prefix,
    )

    return _strip_leading_to_prefix(
        _strip_or_prefix(_strip_optional_prefix(_normalize_unicode(line.strip()).lstrip("-–—− \t")))
    )


def normalize_ingredient(line: str) -> str:
    """Return the canonical grocery item name from a stored or raw ingredient line."""
    from src.grocery_wizard.ingredients.parsed import (
        _normalize_unicode,
        _parse_with_library,
        _prefer_plural_form,
        _should_preserve_raw_line,
        _simplify_parsed_name,
        _strip_parenthetical_notes,
        _strip_size_descriptors,
        _strip_trailing_prep_commas,
    )

    if is_junk_ingredient(line):
        return ""
    if re.search(r"<br\s*/?>", line, re.IGNORECASE):
        parts = re.split(r"<br\s*/?>", line, flags=re.IGNORECASE)
        return "<br/>".join(normalize_ingredient(part) for part in parts if part.strip())

    stripped = line.strip()
    if stripped.startswith("[x]"):
        text = _strip_trailing_prep_commas(_normalize_unicode(stripped))
        text = re.sub(r",\s*optional\s*$", "", text, flags=re.IGNORECASE).strip()
        return text.lower()
    if stripped.startswith(("▢", "•", "*")):
        bullet = stripped[0]
        content = stripped[1:].strip()
        formatted = format_ingredient_for_storage(content) or _strip_trailing_prep_commas(content)
        return f"{bullet} {formatted}".lower()

    if _should_preserve_raw_line(line):
        parse_text = _strip_parenthetical_notes(_prepare_line_for_parsing(line))
        if not parse_text:
            return ""
        parsed = _parse_with_library(parse_text)
        name = _simplify_parsed_name(parsed.name[0].text) if parsed.name else parse_text
        name = _prefer_plural_form(_strip_size_descriptors(name))
        if re.search(r"\b1\b", line) and " cube" in line.lower() and name.endswith("cubes"):
            name = name[:-1]
        return name.lower()

    if looks_like_stored_ingredient_line(_prepare_line_for_parsing(line)):
        name, _ = _parse_stored_ingredient(_prepare_line_for_parsing(line))
        return name.lower()

    stored = format_ingredient_for_storage(line)
    if not stored:
        return ""
    name, _ = _parse_stored_ingredient(stored)
    return name.lower()


def parse_amount(line: str) -> tuple[str, str | None]:
    """Parse an ingredient line into ``(name, amount | None)``."""
    if is_junk_ingredient(line):
        return "", None
    text = _prepare_line_for_parsing(line)
    if text and not looks_like_stored_ingredient_line(text):
        stored = format_ingredient_for_storage(line)
        if not stored:
            return "", None
        name, amount = _parse_stored_ingredient(stored)
        if name == "garlic" and amount is None:
            clove_count = garlic_clove_count_from_line(line)
            if clove_count is not None:
                return name, f"clove:{_format_qty(clove_count)}"
        return name, amount
    return _parse_stored_ingredient(text)


def ingredient_name(line: str) -> str:
    return normalize_ingredient(line)
