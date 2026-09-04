"""Internal cleaning helpers for ingredient normalization."""

from __future__ import annotations

import re

from src.grocery_wizard.ingredients._patterns import (
    _CONJUNCTION_SPLIT_RE,
    _DIMENSION_PREP_SEGMENT_RE,
    _INSTRUCTION_ONLY_RE,
    _JUNK_ONLY_PHRASES,
    _PREP_ALTERNATIVE_RE,
    _PREP_WORDS,
    _QUANTITY_RE,
    _SIZES,
    _STANDALONE_INGREDIENT_WORDS,
    _TRAILING_CLAUSE_RE,
    _UNICODE_DASHES,
    _UNICODE_FRACTIONS,
    _UNITS,
    _UNSPLIT_AND_PHRASES,
)


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


def _split_compound_parts_recursive(text: str) -> list[str]:
    split = _try_split_on_conjunction(text)
    if split is None:
        return [text]
    left, right = split
    return _split_compound_parts_recursive(left) + _split_compound_parts_recursive(right)


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


def _split_leading_capitalized_ingredient(piece: str) -> list[str]:
    """``Salt fresh black pepper`` → ``Salt`` + ``fresh black pepper``."""
    words = piece.split(None, 1)
    if len(words) != 2:
        return [piece]
    first, rest = words
    if first[0].isupper() and rest[0].islower() and first.lower() in _STANDALONE_INGREDIENT_WORDS:
        return [first, rest]
    return [piece]


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


def _prepare_line_for_parsing(line: str) -> str:
    from src.grocery_wizard.ingredients.parsed import (
        _normalize_unicode,
        _strip_leading_to_prefix,
        _strip_optional_prefix,
        _strip_or_prefix,
    )

    return _strip_leading_to_prefix(
        _strip_or_prefix(_strip_optional_prefix(_normalize_unicode(line.strip()).lstrip("-–—− \t")))  # noqa: RUF001
    )
