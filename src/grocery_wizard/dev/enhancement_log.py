"""Local enhancement backlog — store and retrieve feature ideas for later agent use."""

from __future__ import annotations

__all__ = [
    "AREA_FILES",
    "ENHANCEMENT_LOG_PATH",
    "add_enhancement",
    "close_enhancement",
    "complete_enhancement",
    "format_pr_title",
    "format_worker_spawn_message",
    "get_enhancement",
    "list_enhancements",
    "list_worker_spawns",
]

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

ENHANCEMENT_LOG_PATH = Path("src/grocery_wizard/dev/enhancements.jsonl")
_LEGACY_ENHANCEMENT_LOG_PATH = Path(".local/grocery_wizard/enhancements.jsonl")

AREA_FILES: dict[str, list[str]] = {
    "ui": ["src/grocery_wizard/ui/app.py"],
    "parser": [
        "src/grocery_wizard/ingredients/normalize.py",
        "src/grocery_wizard/ingredients/_patterns.py",
    ],
    "shopping": [
        "src/grocery_wizard/shopping/grocery_list.py",
        "src/grocery_wizard/shopping/pantry.py",
    ],
    "recipes": [
        "src/grocery_wizard/recipes/add_recipe.py",
        "src/grocery_wizard/recipes/scraper.py",
    ],
    "cli": ["src/grocery_wizard/cli/main.py"],
    "other": [],
}

VALID_AREAS = list(AREA_FILES.keys())


def _resolve_log_path(path: Path) -> Path:
    """Use committed backlog; one-time copy from legacy ``.local/`` if needed."""
    if path != ENHANCEMENT_LOG_PATH:
        return path
    if ENHANCEMENT_LOG_PATH.exists():
        return ENHANCEMENT_LOG_PATH
    legacy = _LEGACY_ENHANCEMENT_LOG_PATH
    if legacy.exists() and legacy.stat().st_size > 0:
        ENHANCEMENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, ENHANCEMENT_LOG_PATH)
    return ENHANCEMENT_LOG_PATH


def _load_all(path: Path) -> list[dict]:
    path = _resolve_log_path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    entries = []
    with path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _save_all(entries: list[dict], path: Path) -> None:
    path = _resolve_log_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _next_id(entries: list[dict]) -> str:
    max_num = 0
    for entry in entries:
        eid = entry.get("id", "")
        if eid.startswith("enh_"):
            try:
                num = int(eid[4:])
                max_num = max(max_num, num)
            except ValueError:
                pass
    return f"enh_{max_num + 1:03d}"


def add_enhancement(
    title: str,
    description: str = "",
    area: str = "other",
    *,
    path: Path = ENHANCEMENT_LOG_PATH,
) -> str:
    """Append a new enhancement entry and return its assigned ID."""
    entries = _load_all(path)
    new_id = _next_id(entries)
    entry = {
        "id": new_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "open",
        "title": title,
        "description": description,
        "area": area,
        "tags": [],
    }
    path = _resolve_log_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return new_id


def list_enhancements(
    *,
    include_closed: bool = False,
    path: Path = ENHANCEMENT_LOG_PATH,
) -> list[dict]:
    """Return enhancements newest-first, optionally including closed/done ones."""
    entries = _load_all(path)
    if not include_closed:
        entries = [e for e in entries if e.get("status") == "open"]
    return list(reversed(entries))


def get_enhancement(eid: str, *, path: Path = ENHANCEMENT_LOG_PATH) -> dict | None:
    """Return a single enhancement by ID, or None if not found."""
    for entry in _load_all(path):
        if entry.get("id") == eid:
            return entry
    return None


def close_enhancement(eid: str, *, path: Path = ENHANCEMENT_LOG_PATH) -> bool:
    """Set status to 'done' without a PR link. Prefer complete_enhancement when shipping."""
    return complete_enhancement(eid, pr_url=None, path=path)


def format_pr_title(entry: dict, *, max_len: int = 256) -> str:
    """GitHub PR title: ``{enh_id}: {title}`` (truncated to GitHub's limit)."""
    eid = entry.get("id") or "enh_???"
    title = (entry.get("title") or "").strip()
    prefix = f"{eid}: "
    room = max_len - len(prefix)
    if room < 1:
        return prefix[:max_len]
    if len(title) > room:
        title = title[: room - 1].rstrip() + "…"
    return prefix + title


def complete_enhancement(
    eid: str,
    *,
    pr_url: str | None = None,
    path: Path = ENHANCEMENT_LOG_PATH,
) -> bool:
    """Mark done; optionally store ``pr_url`` and ``completed_at``. Returns True if updated."""
    entries = _load_all(path)
    found = False
    for entry in entries:
        if entry.get("id") == eid:
            entry["status"] = "done"
            entry["completed_at"] = datetime.now(UTC).isoformat()
            if pr_url:
                entry["pr_url"] = pr_url.strip()
            found = True
            break
    if found:
        _save_all(entries, path)
    return found


def title_to_branch_slug(title: str, *, max_len: int = 40) -> str:
    """Derive a git branch slug from an enhancement title."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        slug = "enhancement"
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug


def format_worker_spawn_message(entry: dict) -> str:
    """First user message to start a dedicated agent run for one backlog item."""
    eid = entry.get("id", "")
    title = entry.get("title", "").strip()
    if title:
        return f"/work-on-enhancement {eid} — {title}"
    return f"/work-on-enhancement {eid}"


def list_worker_spawns(
    *,
    path: Path | None = None,
) -> list[dict]:
    """One spawn spec per open enhancement (newest-first, same order as list_enhancements)."""
    log_path = ENHANCEMENT_LOG_PATH if path is None else path
    specs: list[dict] = []
    for entry in list_enhancements(path=log_path):
        title = entry.get("title", "")
        slug = title_to_branch_slug(title)
        specs.append(
            {
                "id": entry.get("id"),
                "title": title,
                "area": entry.get("area", "other"),
                "branch": f"cursor/{slug}-21af",
                "agent_message": format_worker_spawn_message(entry),
                "prompt": format_agent_prompt(entry),
            }
        )
    return specs


def format_agent_prompt(entry: dict) -> str:
    """Return a ready-to-paste agent prompt for the given enhancement entry."""
    area = entry.get("area", "other")
    files = AREA_FILES.get(area, [])
    if files:
        files_text = "\n".join(f"  - {f}" for f in files)
    else:
        files_text = "  (no specific files mapped for this area)"

    title = entry.get("title", "")
    eid = entry.get("id", "")
    slug = title_to_branch_slug(title)
    branch = f"cursor/{slug}-21af"

    boilerplate = (
        "You are working in the grocery_wizard repo. "
        "Read the relevant files first, then implement the following enhancement:"
    )
    lines = [
        boilerplate,
        "",
        f"**ID:** {eid}",
        f"**Title:** {title}",
    ]
    desc = entry.get("description", "").strip()
    if desc:
        lines += ["", "**Description:**", desc]
    lines += [
        "",
        f"**Area:** {area}",
        "",
        "**Relevant files to read first:**",
        files_text,
        "",
        "**Git workflow:**",
        f"- Fetch `origin/main`, then create branch `{branch}` off `main`.",
        "- Implement with focused commits; run `uv run ruff check` on touched Python.",
        "",
        "**Ship (you must do this — user does not manage the backlog):**",
        f"- PR title: `… dev enhancement-pr-title {eid}` → use output as GitHub PR title.",
        "- Push; create or update the PR for this branch.",
        f"- Done + PR link: `… dev complete-enhancement {eid}` (`gh pr view` or `--pr-url`).",
        f"- Verify: `… dev list-enhancements --all` shows {eid} [done] and PR URL.",
        "",
        "Full commands use: uv run python -m src.grocery_wizard",
        "More: .cursor/commands/work-on-enhancement.md",
    ]
    return "\n".join(lines)
