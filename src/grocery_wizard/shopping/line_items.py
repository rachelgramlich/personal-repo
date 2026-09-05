"""Shared helpers for parsing and normalising user-entered line items.

This module is the single source of truth for stripping bullet/checkbox
prefixes from pasted text.  Other modules (e.g. dedup/sort in #35, aisle
classification in #36) should import :func:`strip_line_item` and
:func:`parse_line_items` from here rather than duplicating the logic.
"""

from __future__ import annotations

import re

_NUMBERED_CHECKLIST_RE = re.compile(r"^\d+\.\s*(?:\[\s*[xX]?\s*\]\s*)?")
_BULLET_CHECKLIST_RE = re.compile(r"^[-–—−•*]\s*(?:\[\s*[xX]?\s*\]\s*)?")  # noqa: RUF001
_BARE_CHECKLIST_RE = re.compile(r"^\[\s*[xX]?\s*\]\s*")


def strip_line_item(line: str) -> str:
    """Remove bullet/checkbox prefix and surrounding whitespace from a single line.

    Examples::

        strip_line_item("- [ ] Flowers")  # -> "Flowers"
        strip_line_item("- [x] Milk")     # -> "Milk"
        strip_line_item("[ ] Eggs")       # -> "Eggs"
        strip_line_item("- Bread")        # -> "Bread"
        strip_line_item("1. [ ] Apples") # -> "Apples"
        strip_line_item("Sugar")          # -> "Sugar"
    """
    stripped = line.strip()
    if not stripped:
        return ""
    stripped = _NUMBERED_CHECKLIST_RE.sub("", stripped)
    stripped = _BULLET_CHECKLIST_RE.sub("", stripped)
    stripped = _BARE_CHECKLIST_RE.sub("", stripped)
    return stripped.strip()


# Backward-compatible alias used by aisle classification and grocery normalization.
strip_checklist_prefix = strip_line_item


def parse_line_items(text: str) -> list[str]:
    """Split *text* on newlines and return normalised, non-empty items.

    Lines that are blank or start with ``#`` (comments) are ignored.
    Each remaining line is passed through :func:`strip_line_item`.
    """
    result: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        item = strip_line_item(stripped)
        if item:
            result.append(item)
    return result
