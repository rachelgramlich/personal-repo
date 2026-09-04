"""Collect and persist optional CLI feedback after production commands."""

from __future__ import annotations

__all__ = [
    "PROD_COMMANDS",
    "FeedbackEntry",
    "append_feedback",
    "format_feedback_list",
    "list_feedback",
    "load_feedback",
    "prompt_for_feedback",
]

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from src.grocery_wizard.config import FEEDBACK_PATH


class FeedbackEntry(TypedDict):
    timestamp: str
    command: str
    feedback: str


PROD_COMMANDS = frozenset(
    {
        "add-recipe",
        "plan-recipes",
        "create-grocery-list",
        "edit-pantry",
    }
)


def load_feedback(path: Path = FEEDBACK_PATH) -> list[FeedbackEntry]:
    """Load feedback entries from disk, or return an empty list if missing/corrupt."""
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: could not read feedback file ({path}): {exc}", file=sys.stderr)
        print("Starting with an empty feedback log.", file=sys.stderr)
        return []

    if not isinstance(data, list):
        print(f"Warning: feedback file ({path}) is not a JSON array.", file=sys.stderr)
        print("Starting with an empty feedback log.", file=sys.stderr)
        return []

    return data


def append_feedback(command: str, feedback: str, path: Path = FEEDBACK_PATH) -> None:
    """Append one feedback entry and persist to disk."""
    entries = load_feedback(path)
    entries.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "command": command,
            "feedback": feedback,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def prompt_for_feedback(
    command: str,
    *,
    prompt_fn: Callable[[str], str] = input,
    path: Path = FEEDBACK_PATH,
) -> None:
    """Ask for optional feedback; skip silently on empty input or interrupt."""
    try:
        answer = prompt_fn("Any feedback on this run? (press Enter to skip): ")
    except (EOFError, KeyboardInterrupt):
        return

    text = answer.strip()
    if not text:
        return

    append_feedback(command, text, path)


def format_feedback_list(entries: list[FeedbackEntry]) -> str:
    """Format entries newest-first for display."""
    if not entries:
        return "No feedback yet."

    lines: list[str] = []
    for entry in reversed(entries):
        timestamp = entry.get("timestamp", "?")
        cmd = entry.get("command", "?")
        feedback = entry.get("feedback", "")
        lines.append(f"[{timestamp}] {cmd}: {feedback}")
    return "\n".join(lines)


def list_feedback(path: Path = FEEDBACK_PATH) -> str:
    """Return formatted feedback entries, newest first."""
    return format_feedback_list(load_feedback(path))
