"""Regex patterns and lookup tables for ingredient normalization."""

from __future__ import annotations

import re

# Leading quantity: integers, fractions, mixed numbers, ranges.
_QUANTITY_RE = re.compile(
    r"^[\d\s./-]+|^(?:a|an)\s+",
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

_UNICODE_DASHES = ("–", "—", "−")  # en-dash, em-dash, minus sign  # noqa: RUF001

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
    r"^((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s+to\s+((?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s+",
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
