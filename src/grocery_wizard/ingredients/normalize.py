"""Rule-based ingredient normalization for grocery lists."""

from __future__ import annotations

import math
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
    r"\b(?:plus more for|such as|or to taste|to taste|for garnish|optional|"
    r"as needed|if needed|for serving|for topping|to serve)\b.*",
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
    r"(?:\s+into)?(?:\s+(?:\d+[- ]inch\s+)?pieces?)?"
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


def should_show_amount(amount: str | None, raw_line: str) -> bool:
    """Return whether a parsed amount should appear on the grocery list."""
    if amount is None:
        return False
    return _HIDE_AMOUNT_UNITS_RE.search(raw_line) is None


def is_junk_ingredient(line: str) -> bool:
    """Return True when a line is only prep instructions, not a grocery item."""
    return _is_junk_only(line)


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


def normalize_ingredient(line: str) -> str:
    """Reduce a recipe ingredient line to a grocery-store item name."""
    text = _normalize_unicode_dashes(line.strip().lower())
    if not text:
        return ""

    text = _strip_optional_prefix(text)
    if not text:
        return ""

    if _is_junk_only(text):
        return ""

    text = re.sub(r"\([^)]*\)", "", text)
    text = _ingredient_base_text(text)
    text = _TRAILING_CLAUSE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()

    preserved_product = _match_preserved_product(text)

    text = _strip_leading_amount(text)
    words = text.split()
    changed = True
    while changed and words:
        changed = False
        before = len(words)
        words = _strip_leading_tokens(words, _UNITS | _SIZES)
        while words and words[0].rstrip(".,") in _PREP_WORDS:
            if words[0] in {"frozen", "canned", "dried"} and len(words) > 1:
                break
            words.pop(0)
        if len(words) != before:
            changed = True
    text = " ".join(words).strip()

    text = _simplify_ingredient_name(text)
    text = _strip_trailing_cut_instructions(text)
    text = _strip_trailing_prep(text)
    text = _strip_incomplete_prep_suffix(text)
    text = _strip_leading_prep(text)
    text = _simplify_herb_leaves(text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return ""

    if preserved_product:
        return preserved_product

    return _prefer_plural_form(text)


def _ingredient_base_text(text: str) -> str:
    """Keep the full ingredient name when commas separate descriptors, not trailing prep."""
    without_parens = re.sub(r"\([^)]*\)", "", text).strip()
    segments = [segment.strip() for segment in without_parens.split(",") if segment.strip()]
    if len(segments) <= 1:
        return without_parens
    if all(_is_prep_only_segment(segment) for segment in segments[1:]):
        return segments[0]
    if all(_is_alternative_segment(segment) for segment in segments[1:]):
        return segments[0]

    kept = [segments[0]]
    for segment in segments[1:]:
        if _is_prep_only_segment(segment):
            break
        kept.append(segment)
    if len(kept) == 1:
        return segments[0]
    return " ".join(kept)


def _strip_optional_prefix(text: str) -> str:
    return re.sub(r"^optional:\s*", "", text, flags=re.IGNORECASE).strip()


def _strip_leading_amount(text: str) -> str:
    """Remove leading quantities, including dual measures like ``1 cup/110 grams``."""
    text = re.sub(r"^\d+\s+\w+/\d+\s+\w+\s+", "", text, flags=re.IGNORECASE)
    return _QUANTITY_RE.sub("", text).strip()


def _is_alternative_segment(segment: str) -> bool:
    """Comma-separated protein alternatives: ``turkey``, ``or beef``."""
    cleaned = segment.strip().lower()
    if cleaned.startswith("or "):
        cleaned = cleaned[3:].strip()
    elif len(cleaned.split()) > 2:
        return False
    if not cleaned or _is_prep_only_segment(cleaned):
        return False
    return len(cleaned.split()) <= 2


def _match_preserved_product(text: str) -> str | None:
    lowered = text.lower()
    for product in sorted(_PRESERVED_PRODUCTS, key=len, reverse=True):
        if product in lowered:
            return product

    ground_match = re.search(r"\bground\s+([a-z]+)", lowered)
    if ground_match and ground_match.group(1) in _GROUND_MEATS:
        return f"ground {ground_match.group(1)}"

    for form in sorted(_TOMATO_PREP_FORMS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(form)}\s+tomatoes?\b", lowered):
            if form == "whole peeled":
                return "whole peeled tomatoes"
            return f"{form} tomatoes"

    frozen_match = re.search(r"\bfrozen\s+([a-z]+(?:\s+[a-z]+)?)", lowered)
    if frozen_match:
        return f"frozen {frozen_match.group(1)}"

    return None


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


def _strip_incomplete_prep_suffix(text: str) -> str:
    while True:
        match = _INCOMPLETE_PREP_SUFFIX_RE.search(text)
        if match is None:
            return text.strip(" ,")
        text = text[: match.start()].strip(" ,")


def _strip_trailing_cut_instructions(text: str) -> str:
    changed = True
    while changed:
        changed = False
        updated = _TRAILING_CUT_INSTRUCTION_RE.sub("", text).strip(" ,")
        if updated != text:
            text = updated
            changed = True
    return text


def _simplify_herb_leaves(text: str) -> str:
    match = _HERB_LEAVES_RE.match(text.strip())
    if match:
        return match.group(1).lower()
    return text


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


def _simplify_ingredient_name(text: str) -> str:
    if " or " in text:
        left, _, right = text.partition(" or ")
        right_clean = right.strip()
        left_clean = left.strip()
        if _PREP_ALTERNATIVE_RE.match(right_clean) or _PREP_ALTERNATIVE_RE.match(
            f"{left_clean.split()[-1]} or {right_clean}" if left_clean else right_clean
        ):
            text = left_clean
        elif _is_prep_alternative_phrase(right_clean):
            text = left_clean
        elif _is_prep_alternative_phrase(text):
            return ""
        else:
            text = right_clean
    words = text.split()
    if len(words) >= 2 and words[0] in _DESCRIPTOR_WORDS:
        text = " ".join(words[1:])
    return text.strip()


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
    if segment in _JUNK_ONLY_PHRASES:
        return True
    if _INSTRUCTION_ONLY_RE.match(segment):
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

    if text == "garlic cloves":
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

    # No recognised unit — return a bare count for whole-item ingredients.
    try:
        if _parse_qty(qty_str) > 0:
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
        # Bare counts (no unit) — round up for shopping lists.
        return str(math.ceil(total))

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
