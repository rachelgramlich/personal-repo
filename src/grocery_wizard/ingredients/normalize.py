"""Rule-based ingredient normalization for grocery lists."""

from __future__ import annotations

__all__ = [
    "clean_ingredient_line_for_storage",
    "drop_junk_ingredient_lines",
    "expand_ingredient_line",
    "ingredient_name",
    "is_instruction_line",
    "is_junk_ingredient",
    "is_metadata_line",
    "is_recipe_step_line",
    "normalize_ingredient",
    "parse_amount",
    "split_compound_ingredients",
    "split_merged_ingredient_line",
    "split_recipe_title_bleed",
]

import re

from src.grocery_wizard.ingredients._cleaning import (
    _is_junk_only,
    _normalize_unicode_dashes,
    _normalize_unicode_fractions,
    _prepare_line_for_parsing,
    _split_compound_parts_recursive,
    _split_leading_capitalized_ingredient,
)
from src.grocery_wizard.ingredients._patterns import (
    _CHECKLIST_ITEM_RE,
    _CONJUNCTION_SPLIT_RE,
    _GROCERY_NOUNS,
    _INSTRUCTION_ONLY_RE,
    _INSTRUCTION_VERB_RE,
    _MERGED_CAMEL_SPLIT_RE,
    _MERGED_QTY_SPLIT_RE,
    _METADATA_LINE_RE,
    _RECIPE_STEP_RE,
    _RECIPE_TITLE_FILLER,
    _UNITS,
)
from src.grocery_wizard.ingredients.parsed import (  # noqa: F401
    _format_qty,
    aggregate_amounts,
    format_ingredient_for_storage,
    garlic_clove_count_from_line,
    is_nyt_cooking_url,
    looks_like_stored_ingredient_line,
    minimal_clean_for_storage,
    should_show_amount,
)
from src.grocery_wizard.ingredients.parsed import (
    parse_stored_ingredient as _parse_stored_ingredient,
)


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
    return len(stripped) > 100 and bool(_INSTRUCTION_VERB_RE.search(stripped))


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
    for raw_segment in _MERGED_CAMEL_SPLIT_RE.split(text):
        segment = raw_segment.strip()
        if not segment:
            continue
        for raw_piece in _MERGED_QTY_SPLIT_RE.split(segment):
            piece = raw_piece.strip()
            if not piece:
                continue
            parts.extend(_split_leading_capitalized_ingredient(piece))
    return parts or [text]


def clean_ingredient_line_for_storage(line: str) -> str:
    return format_ingredient_for_storage(line)


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
