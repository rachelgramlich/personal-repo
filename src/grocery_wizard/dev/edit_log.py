"""Log per-recipe ingredient edits from the review UI for later parser improvements."""

from __future__ import annotations

__all__ = ["EDIT_LOG_PATH", "log_ingredient_edits"]

import json
from datetime import UTC, datetime
from pathlib import Path

EDIT_LOG_PATH = Path(".local/grocery_wizard/ingredient_edits.jsonl")


def log_ingredient_edits(
    recipe_name: str,
    original_text: str,
    edited_text: str,
    *,
    path: Path = EDIT_LOG_PATH,
) -> int:
    """Diff original vs edited ingredient text and append a JSONL entry.

    Returns the total number of changed lines (removed + added). Returns 0
    and writes nothing when the texts are identical after normalisation.
    """
    original_lines = [ln.strip() for ln in original_text.splitlines() if ln.strip()]
    edited_lines = [ln.strip() for ln in edited_text.splitlines() if ln.strip()]

    if original_lines == edited_lines:
        return 0

    original_set = set(original_lines)
    edited_set = set(edited_lines)

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "recipe_name": recipe_name,
        "original_lines": original_lines,
        "edited_lines": edited_lines,
        "removed_lines": [ln for ln in original_lines if ln not in edited_set],
        "added_lines": [ln for ln in edited_lines if ln not in original_set],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return len(entry["removed_lines"]) + len(entry["added_lines"])
