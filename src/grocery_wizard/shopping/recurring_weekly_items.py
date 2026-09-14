"""Recurring weekly grocery items — added to every week's list."""

from __future__ import annotations

import sys
from pathlib import Path

from src.grocery_wizard.config import RECURRING_WEEKLY_ITEMS_PATH
from src.grocery_wizard.shopping.line_items import parse_line_items, strip_line_item


def apply_recurring_session_overrides(
    template: list[str],
    *,
    additions: list[str] | None = None,
    removals: set[str] | None = None,
) -> list[str]:
    """Merge per-run recurring additions/removals without changing the saved template."""
    removal_keys = {name.strip().lower() for name in (removals or set()) if name.strip()}
    result: list[str] = []
    seen: set[str] = set()
    for item in template:
        key = item.strip().lower()
        if not key or key in removal_keys or key in seen:
            continue
        seen.add(key)
        result.append(item.strip())
    for item in additions or []:
        cleaned = item.strip()
        key = cleaned.lower()
        if not key or key in removal_keys or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def remove_recurring_weekly_item(search: str, path: Path | None = None) -> bool:
    """Remove the first recurring item whose name matches *search*."""
    items_path = path or RECURRING_WEEKLY_ITEMS_PATH
    items = load_recurring_weekly_items(items_path)
    if not items:
        return False

    lowered = search.strip().lower()
    if not lowered:
        return False

    new_items: list[str] = []
    removed = False
    for item in items:
        if not removed and item.strip().lower() == lowered:
            removed = True
            continue
        new_items.append(item)
    if not removed:
        return False

    write_recurring_weekly_items(items_path, new_items)
    return True


def append_recurring_weekly_item(name: str, path: Path | None = None) -> bool:
    """Append an item to the recurring weekly template if not already present."""
    items_path = path or RECURRING_WEEKLY_ITEMS_PATH
    cleaned = name.strip()
    if not cleaned:
        return False
    items = load_recurring_weekly_items(items_path)
    if any(existing.strip().lower() == cleaned.lower() for existing in items):
        return False
    write_recurring_weekly_items(items_path, [*items, cleaned])
    return True


def load_recurring_weekly_items(path: Path | None = None) -> list[str]:
    """Load recurring weekly items from a text file (one item per line, order preserved)."""
    items_path = path or RECURRING_WEEKLY_ITEMS_PATH
    if not items_path.exists():
        return []

    return parse_line_items(items_path.read_text(encoding="utf-8"))


def write_recurring_weekly_items(path: Path, items: list[str]) -> None:
    """Write recurring weekly items back to disk, preserving a trailing newline."""
    header = "# Recurring weekly items — added to every grocery list (one item per line).\n"
    header += "# Lines starting with # are ignored.\n\n"
    body = "\n".join(item.strip() for item in items if item.strip())
    text = header + body
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def prompt_recurring_weekly_items(
    defaults: list[str] | None = None,
    *,
    path: Path | None = None,
    interactive: bool = True,
) -> list[str]:
    """Show recurring weekly items and let the user accept, edit, or skip for this week."""
    items_path = path or RECURRING_WEEKLY_ITEMS_PATH
    items = list(defaults if defaults is not None else load_recurring_weekly_items(items_path))
    if not interactive:
        return items

    while True:
        print()
        print("Recurring weekly items")
        print("-" * 40)
        if items:
            for index, item in enumerate(items, start=1):
                print(f"  {index}. {item}")
        else:
            print("  (none)")
        print()
        print("[Enter] add to list  [e]dit  [s]kip")
        try:
            choice = input("> ").strip().lower()
        except EOFError:
            return items

        if choice in ("", "a", "add", "y", "yes"):
            return items
        if choice in ("s", "skip", "n", "no"):
            return []
        if choice in ("e", "edit"):
            items = _prompt_edit_lines(items)
            try:
                save = input("Save as defaults for future weeks? [y/N]: ").strip().lower()
            except EOFError:
                save = ""
            if save in ("y", "yes"):
                write_recurring_weekly_items(items_path, items)
                print(f"Saved {items_path}", file=sys.stderr)
            continue

        print("Press Enter to add, 'e' to edit, or 's' to skip.")


def _prompt_edit_lines(items: list[str]) -> list[str]:
    print("Edit list (one item per line; empty line when done):")
    edited: list[str] = []
    while True:
        try:
            line = input().strip()
        except EOFError:
            break
        if not line:
            break
        item = strip_line_item(line)
        if item:
            edited.append(item)
    return edited
