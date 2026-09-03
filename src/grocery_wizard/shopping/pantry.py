"""Pantry staples — items assumed on hand and excluded from grocery lists."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from src.grocery_wizard.config import PANTRY_PATH


def load_pantry(path: Path | None = None) -> set[str]:
    """Load pantry items from a text file (one item per line)."""
    pantry_path = path or PANTRY_PATH
    if not pantry_path.exists():
        return set()

    items: set[str] = set()
    for raw_line in pantry_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().lower()
        if line and not line.startswith("#"):
            items.add(line)
    return items


def is_pantry_item(normalized: str, pantry: set[str]) -> bool:
    """Return True if normalized ingredient matches a pantry item.

    Pantry items match when they appear as a consecutive word phrase in the
    ingredient (e.g. pantry ``salt`` matches ``kosher salt``). We do not match
    the reverse (ingredient word appearing inside a longer pantry phrase like
    ``beef stock``).
    """
    name = normalized.strip().lower()
    if not name:
        return False

    name_words = name.split()
    for item in pantry:
        if name == item:
            return True
        if _contains_word_phrase(name_words, item.split()):
            return True
    return False


def _contains_word_phrase(haystack_words: list[str], needle_words: list[str]) -> bool:
    if not needle_words or len(needle_words) > len(haystack_words):
        return False
    width = len(needle_words)
    for index in range(len(haystack_words) - width + 1):
        if haystack_words[index : index + width] == needle_words:
            return True
    return False


def _matches_pantry_search(search: str, item: str) -> bool:
    """Return True if search term identifies a pantry item by name."""
    lowered_search = search.strip().lower()
    lowered_item = item.strip().lower()
    if not lowered_search or not lowered_item:
        return False
    if lowered_search == lowered_item:
        return True
    if lowered_item.startswith(lowered_search):
        return True

    search_words = lowered_search.split()
    item_words = lowered_item.split()
    return _contains_word_phrase(search_words, item_words) or _contains_word_phrase(
        item_words, search_words
    )


@dataclass
class PantrySection:
    """A section header and its pantry items (line indices into the source file)."""

    header: str | None
    items: list[tuple[int, str]] = field(default_factory=list)


def parse_pantry_file(path: Path) -> tuple[list[str], list[PantrySection]]:
    """Parse pantry.txt into raw lines and display sections."""
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = [
            "# Pantry staples — one item per line.",
            "# Lines starting with # are section headers or comments.",
            "",
            "# --- Uncategorized ---",
        ]

    sections: list[PantrySection] = []
    current = PantrySection(header=None)

    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            if current.header is not None or current.items:
                sections.append(current)
            current = PantrySection(header=raw_line)
        elif stripped:
            current.items.append((index, stripped))

    if current.header is not None or current.items:
        sections.append(current)

    if not sections:
        sections = [PantrySection(header="# --- Uncategorized ---")]

    return lines, sections


def write_pantry_file(path: Path, lines: list[str]) -> None:
    """Write pantry lines back to disk, ensuring a trailing newline."""
    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def format_pantry_display(sections: list[PantrySection]) -> str:
    """Format pantry sections for terminal display."""
    parts: list[str] = []
    item_number = 1
    for section in sections:
        if section.header:
            parts.append(section.header)
        for _index, item in section.items:
            parts.append(f"  {item_number}. {item}")
            item_number += 1
        if section.items:
            parts.append("")
    return "\n".join(parts).rstrip()


def _flatten_items(sections: list[PantrySection]) -> list[tuple[int, str]]:
    return [entry for section in sections for entry in section.items]


def _add_item(lines: list[str], sections: list[PantrySection]) -> None:
    name = input("Item name: ").strip()
    if not name:
        print("Cancelled — empty name.")
        return
    if name.startswith("#"):
        print("Cancelled — item names cannot start with '#'.")
        return

    numbered_sections = [
        (index + 1, section)
        for index, section in enumerate(sections)
        if section.header is not None or section.items
    ]
    if not numbered_sections:
        numbered_sections = [(1, PantrySection(header="# --- Uncategorized ---"))]

    print("\nAdd to section:")
    for number, section in numbered_sections:
        label = section.header or "(no header)"
        print(f"  {number}. {label}")
    print(f"  {len(numbered_sections) + 1}. New section")

    choice = input("Section [#]: ").strip()
    if not choice:
        target = numbered_sections[-1][1]
    else:
        try:
            picked = int(choice)
        except ValueError:
            print("Cancelled — invalid section.")
            return
        if picked == len(numbered_sections) + 1:
            header = input("New section header (e.g. # --- Spices ---): ").strip()
            if not header:
                header = "# --- Uncategorized ---"
            elif not header.startswith("#"):
                header = f"# {header}"
            target = PantrySection(header=header)
            sections.append(target)
            lines.append(header)
        elif 1 <= picked <= len(numbered_sections):
            target = numbered_sections[picked - 1][1]
        else:
            print("Cancelled — invalid section.")
            return

    insert_at = len(lines)
    if target.items:
        insert_at = target.items[-1][0] + 1
    elif target.header is not None:
        try:
            insert_at = lines.index(target.header) + 1
        except ValueError:
            insert_at = len(lines)

    lines.insert(insert_at, name)
    _reindex_sections(lines, sections)


def _remove_item(lines: list[str], sections: list[PantrySection]) -> None:
    flat = _flatten_items(sections)
    if not flat:
        print("No items to remove.")
        return

    choice = input("Item # or name to remove: ").strip()
    if not choice:
        print("Cancelled.")
        return

    line_index: int | None = None
    if choice.isdigit():
        number = int(choice)
        if 1 <= number <= len(flat):
            line_index = flat[number - 1][0]
    else:
        matches = [(index, item) for index, item in flat if _matches_pantry_search(choice, item)]
        if len(matches) == 1:
            line_index = matches[0][0]
        elif len(matches) > 1:
            print("Multiple matches:")
            for index, (_line_idx, item) in enumerate(matches, start=1):
                print(f"  {index}. {item}")
            pick = input("Pick match #: ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(matches):
                line_index = matches[int(pick) - 1][0]
            else:
                print("Cancelled.")
                return
        else:
            print(f"No match for '{choice}'.")
            return

    if line_index is None:
        print("Cancelled — invalid item.")
        return

    removed = lines.pop(line_index)
    print(f"Removed: {removed}")
    _reindex_sections(lines, sections)


def _reindex_sections(lines: list[str], sections: list[PantrySection]) -> None:
    _, sections[:] = parse_pantry_file_from_lines(lines)


def parse_pantry_file_from_lines(lines: list[str]) -> tuple[list[str], list[PantrySection]]:
    """Re-parse in-memory pantry lines (same rules as parse_pantry_file)."""
    sections: list[PantrySection] = []
    current = PantrySection(header=None)

    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            if current.header is not None or current.items:
                sections.append(current)
            current = PantrySection(header=raw_line)
        elif stripped:
            current.items.append((index, stripped))

    if current.header is not None or current.items:
        sections.append(current)

    if not sections:
        sections = [PantrySection(header="# --- Uncategorized ---")]

    return lines, sections


def _open_in_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR", "vi")
    try:
        subprocess.run([*shlex.split(editor), str(path)], check=False)
    except FileNotFoundError:
        print(f"Editor not found: {editor}", file=sys.stderr)


def run_pantry_interactive(path: Path | None = None) -> int:
    """Show pantry grouped by section; add, remove, or edit in $EDITOR."""
    pantry_path = path or PANTRY_PATH
    lines, sections = parse_pantry_file(pantry_path)

    while True:
        print()
        print("Pantry staples")
        print("=" * 40)
        print(format_pantry_display(sections))
        print()
        print("[a]dd  [r]emove  [e]ditor  [q]uit")
        choice = input("> ").strip().lower()

        if choice in ("q", "quit"):
            write_pantry_file(pantry_path, lines)
            print(f"Saved {pantry_path}")
            return 0
        if choice in ("a", "add"):
            _add_item(lines, sections)
            continue
        if choice in ("r", "remove"):
            _remove_item(lines, sections)
            continue
        if choice in ("e", "edit", "editor"):
            write_pantry_file(pantry_path, lines)
            _open_in_editor(pantry_path)
            lines, sections = parse_pantry_file(pantry_path)
            continue

        print("Unknown option. Use a, r, e, or q.")
