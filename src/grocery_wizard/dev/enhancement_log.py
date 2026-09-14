"""Enhancement backlog — GitHub Issues (default) or JSONL file (tests only)."""

from __future__ import annotations

__all__ = [
    "AREA_FILES",
    "add_enhancement",
    "close_enhancement",
    "format_pr_title",
    "format_worker_spawn_message",
    "get_enhancement",
    "list_enhancements",
    "list_worker_spawns",
    "migrate_jsonl_to_github",
    "record_manual_verification",
]

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from src.grocery_wizard.dev import enhancement_github as gh

# Legacy paths for one-time migration and tests (not the committed backlog).
_LEGACY_COMMITTED_JSONL = Path("src/grocery_wizard/dev/enhancements.jsonl")
_LEGACY_LOCAL_JSONL = Path(".local/grocery_wizard/enhancements.jsonl")

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


def _load_all_file(path: Path) -> list[dict]:
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


def _save_all_file(entries: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _next_id_file(entries: list[dict]) -> str:
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


def _add_enhancement_file(
    title: str,
    description: str,
    area: str,
    path: Path,
) -> str:
    entries = _load_all_file(path)
    new_id = _next_id_file(entries)
    entry = {
        "id": new_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "open",
        "title": title,
        "description": description,
        "area": area,
        "tags": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return new_id


def add_enhancement(
    title: str,
    description: str = "",
    area: str = "other",
    *,
    path: Path | None = None,
) -> str:
    """Create a backlog item; returns GitHub issue number as string (file tests: ``enh_NNN``)."""
    return create_enhancement(title, description, area, path=path)["id"]


def create_enhancement(
    title: str,
    description: str = "",
    area: str = "other",
    *,
    path: Path | None = None,
) -> dict:
    """Create a backlog item; returns entry metadata (includes ``issue_url`` on GitHub)."""
    if path is not None:
        new_id = _add_enhancement_file(title, description, area, path)
        entry = get_enhancement(new_id, path=path)
        return entry or {"id": new_id, "title": title, "area": area}
    entry = gh.create_issue(title, description, area)
    if not entry.get("issue_number"):
        raise RuntimeError("GitHub issue created but issue number missing.")
    entry["id"] = str(entry["issue_number"])
    return entry


def list_enhancements(
    *,
    include_closed: bool = False,
    path: Path | None = None,
) -> list[dict]:
    if path is not None:
        entries = _load_all_file(path)
        if not include_closed:
            entries = [e for e in entries if e.get("status") == "open"]
        return list(reversed(entries))
    return gh.list_issues(include_closed=include_closed)


def get_enhancement(eid: str, *, path: Path | None = None) -> dict | None:
    if path is not None:
        for entry in _load_all_file(path):
            if entry.get("id") == eid:
                return entry
        return None
    return gh.get_issue(eid)


def close_enhancement(eid: str, *, path: Path | None = None) -> bool:
    if path is not None:
        entries = _load_all_file(path)
        found = False
        for entry in entries:
            if entry.get("id") == eid:
                entry["status"] = "done"
                entry["completed_at"] = datetime.now(UTC).isoformat()
                found = True
                break
        if found:
            _save_all_file(entries, path)
        return found
    return gh.close_issue(eid, pr_url=None)


def format_pr_title(entry: dict, *, max_len: int = 256) -> str:
    num = entry.get("issue_number")
    eid = (entry.get("id") or "").strip()
    if num is not None:
        prefix = f"#{num}: "
    elif eid.isdigit():
        prefix = f"#{eid}: "
    elif eid:
        prefix = f"{eid}: "
    else:
        prefix = "issue: "
    title = (entry.get("title") or "").strip()
    room = max_len - len(prefix)
    if room < 1:
        return prefix[:max_len]
    if len(title) > room:
        title = title[: room - 1].rstrip() + "…"
    return prefix + title


def record_manual_verification(
    *,
    pr_url: str,
    issue_number: str | None = None,
    note: str = "",
) -> None:
    """Post a PR comment that manual UAT passed (after user confirms in agent chat)."""
    extra = note.strip()
    issue_bit = f" (issue #{issue_number})" if issue_number else ""
    text = f"**Manual verification:** passed (user confirmed in agent chat){issue_bit}."
    if extra:
        text = f"{text}\n\n{extra}"
    gh.comment_on_pr(pr_url, text)


def title_to_branch_slug(title: str, *, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        slug = "enhancement"
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug


def format_worker_spawn_message(entry: dict) -> str:
    ref = entry.get("issue_number") or entry.get("id") or ""
    title = entry.get("title", "").strip()
    if title and ref:
        return f"/work-on-enhancement {ref} — {title}"
    if ref:
        return f"/work-on-enhancement {ref}"
    return "/work-on-enhancement"


def list_worker_spawns(*, path: Path | None = None) -> list[dict]:
    specs: list[dict] = []
    for entry in list_enhancements(path=path):
        title = entry.get("title", "")
        slug = title_to_branch_slug(title)
        eid = entry.get("id") or entry.get("issue_number")
        specs.append(
            {
                "id": eid,
                "title": title,
                "area": entry.get("area", "other"),
                "branch": f"cursor/{slug}-21af",
                "agent_message": format_worker_spawn_message(entry),
                "prompt": format_agent_prompt(entry),
            }
        )
    return specs


def format_agent_prompt(entry: dict) -> str:
    area = entry.get("area", "other")
    files = AREA_FILES.get(area, [])
    if files:
        files_text = "\n".join(f"  - {f}" for f in files)
    else:
        files_text = "  (no specific files mapped for this area)"

    title = entry.get("title", "")
    issue_num = entry.get("issue_number")
    eid = str(issue_num) if issue_num is not None else (entry.get("id") or "")
    issue_ref = entry.get("issue_url") or ""
    slug = title_to_branch_slug(title)
    branch = f"cursor/{slug}-21af"

    boilerplate = (
        "You are working in the grocery_wizard repo. "
        "Read the relevant files first, then implement the following enhancement:"
    )
    lines = [
        boilerplate,
        "",
        f"**Issue:** #{eid}" if eid.isdigit() else f"**ID:** {eid}",
        f"**Title:** {title}",
    ]
    if issue_ref:
        lines.append(f"**GitHub issue:** {issue_ref}")
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
        f"- PR title: `uv run python -m src.grocery_wizard dev enhancement-pr-title {eid}`",
        "- Push; create or update the PR using the repo PR template (**Manual verification**).",
        f"- PR body must include `Closes #{eid}` (GitHub closes the issue on merge).",
        "- Tell the user to run **Manual verification** from the PR; echo that section.",
        (
            "- When the user confirms manual passed, post sign-off on the PR: "
            f"`uv run python -m src.grocery_wizard dev record-manual-verification {eid}`"
        ),
        "",
        "More: .cursor/commands/work-on-enhancement.md",
    ]
    return "\n".join(lines)


def _jsonl_migration_paths() -> list[Path]:
    return [
        p
        for p in (_LEGACY_COMMITTED_JSONL, _LEGACY_LOCAL_JSONL)
        if p.exists() and p.stat().st_size > 0
    ]


def migrate_jsonl_to_github(*, dry_run: bool = False) -> list[dict]:
    """Import legacy JSONL rows into GitHub Issues; returns created issue summaries."""
    created: list[dict] = []
    seen_titles: set[str] = set()
    existing_titles = {
        (e.get("title") or "").strip().lower()
        for e in gh.list_issues(include_closed=True)
    }
    for path in _jsonl_migration_paths():
        for row in _load_all_file(path):
            title = (row.get("title") or row.get("id") or "").strip()
            if not title or title.lower() in seen_titles:
                continue
            if title.lower() in existing_titles:
                continue
            seen_titles.add(title.lower())
            description = row.get("description") or ""
            area = row.get("area") or "other"
            if area not in VALID_AREAS:
                area = "other"
            if dry_run:
                created.append({"title": title, "dry_run": True})
                continue
            issue = gh.create_issue(
                title,
                description,
                area,
                closed=row.get("status") == "done",
                pr_url=row.get("pr_url") or "",
                completed_at=row.get("completed_at") or "",
            )
            created.append(
                {
                    "number": issue.get("issue_number"),
                    "url": issue.get("issue_url"),
                    "title": title,
                }
            )
    return created
