"""GitHub Issues backend for the grocery_wizard enhancement backlog."""

from __future__ import annotations

import json
import re
import subprocess
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

ENHANCEMENT_LABEL = "grocery-wizard-enhancement"
AREA_LABEL_PREFIX = "gw-area-"

_ENH_ID_RE = re.compile(r"^\s*enh_\d{3}\s*$", re.IGNORECASE)
_ENH_ID_BODY_RE = re.compile(
    r"\*\*Enhancement ID:\*\*\s*`?(enh_\d{3})`?",
    re.IGNORECASE,
)
_AREA_BODY_RE = re.compile(r"\*\*Area:\*\*\s*(\w+)", re.IGNORECASE)
_PR_BODY_RE = re.compile(r"\*\*PR:\*\*\s*(https?://\S+)", re.IGNORECASE)


class GhError(RuntimeError):
    pass


def _run_gh(args: list[str], *, input_text: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=False,
            input=input_text,
        )
    except FileNotFoundError as exc:
        raise GhError("GitHub CLI (`gh`) is not installed or not on PATH.") from exc
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise GhError(err or f"gh exited {result.returncode}")
    return result.stdout.strip()


def area_to_label(area: str) -> str:
    return f"{AREA_LABEL_PREFIX}{area}"


def label_to_area(labels: list[str]) -> str:
    for label in labels:
        if label.startswith(AREA_LABEL_PREFIX):
            return label[len(AREA_LABEL_PREFIX) :]
    return "other"


def format_issue_body(
    *,
    enh_id: str,
    area: str,
    description: str,
    pr_url: str = "",
    completed_at: str = "",
) -> str:
    desc = (description or "").strip()
    lines: list[str] = []
    if desc:
        lines.append(desc)
        lines.append("")
    lines.append("---")
    lines.append(f"**Enhancement ID:** `{enh_id}`")
    lines.append(f"**Area:** {area}")
    if pr_url:
        lines.append(f"**PR:** {pr_url.strip()}")
    if completed_at:
        lines.append(f"**Completed:** {completed_at}")
    return "\n".join(lines)


def parse_issue_body(body: str) -> dict[str, str]:
    text = body or ""
    enh_match = _ENH_ID_BODY_RE.search(text)
    area_match = _AREA_BODY_RE.search(text)
    pr_match = _PR_BODY_RE.search(text)
    description = text.split("\n---\n", 1)[0].strip()
    return {
        "description": description,
        "id": enh_match.group(1).lower() if enh_match else "",
        "area_from_body": area_match.group(1).lower() if area_match else "",
        "pr_url": pr_match.group(1).strip() if pr_match else "",
    }


def _issue_to_entry(issue: dict[str, Any]) -> dict[str, Any]:
    labels = issue.get("labels") or []
    label_names = [lb.get("name", "") for lb in labels if isinstance(lb, dict)]
    parsed = parse_issue_body(issue.get("body") or "")
    state = (issue.get("state") or "OPEN").upper()
    area = parsed.get("area_from_body") or label_to_area(label_names)
    eid = parsed.get("id") or ""
    return {
        "id": eid,
        "issue_number": issue.get("number"),
        "issue_url": issue.get("url") or "",
        "timestamp": issue.get("createdAt") or "",
        "status": "open" if state == "OPEN" else "done",
        "title": issue.get("title") or "",
        "description": parsed.get("description") or "",
        "area": area,
        "tags": [],
        "pr_url": parsed.get("pr_url") or "",
    }


def _fetch_issues(*, state: str) -> list[dict[str, Any]]:
    """state: OPEN, CLOSED, or ALL."""
    raw = _run_gh(
        [
            "issue",
            "list",
            "--label",
            ENHANCEMENT_LABEL,
            "--state",
            state,
            "--limit",
            "500",
            "--json",
            "number,title,body,state,createdAt,url,labels",
        ]
    )
    if not raw:
        return []
    return json.loads(raw)


def list_issues(*, include_closed: bool = False) -> list[dict[str, Any]]:
    if include_closed:
        open_issues = _fetch_issues(state="OPEN")
        closed_issues = _fetch_issues(state="CLOSED")
        issues = open_issues + closed_issues
        issues.sort(key=lambda i: i.get("createdAt") or "", reverse=True)
        return [_issue_to_entry(i) for i in issues]
    issues = _fetch_issues(state="OPEN")
    issues.sort(key=lambda i: i.get("createdAt") or "", reverse=True)
    return [_issue_to_entry(i) for i in issues]


def _normalize_lookup_id(raw: str) -> str:
    return raw.strip().removeprefix("#")


def get_issue(raw_id: str) -> dict[str, Any] | None:
    lookup = _normalize_lookup_id(raw_id)
    if lookup.isdigit():
        issue = _view_issue(lookup)
        label_names = [lb.get("name", "") for lb in issue.get("labels") or []]
        if ENHANCEMENT_LABEL not in label_names:
            return None
        return _issue_to_entry(issue)

    if not _ENH_ID_RE.match(lookup):
        lookup = lookup.lower()
    for entry in list_issues(include_closed=True):
        if entry.get("id", "").lower() == lookup.lower():
            return entry
    return None


def _next_enh_id(entries: list[dict[str, Any]]) -> str:
    max_num = 0
    for entry in entries:
        eid = entry.get("id") or ""
        if eid.startswith("enh_"):
            with suppress(ValueError):
                max_num = max(max_num, int(eid[4:]))
    return f"enh_{max_num + 1:03d}"


def _issue_number_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def _view_issue(number: str | int) -> dict[str, Any]:
    raw = _run_gh(
        [
            "issue",
            "view",
            str(number),
            "--json",
            "number,title,body,state,createdAt,url,labels",
        ]
    )
    return json.loads(raw)


def create_issue(
    title: str,
    description: str,
    area: str,
    *,
    enh_id: str | None = None,
    closed: bool = False,
    pr_url: str = "",
    completed_at: str = "",
) -> dict[str, Any]:
    if not enh_id:
        existing = list_issues(include_closed=True)
        enh_id = _next_enh_id(existing)
    body = format_issue_body(
        enh_id=enh_id,
        area=area,
        description=description,
        pr_url=pr_url,
        completed_at=completed_at,
    )
    labels = [ENHANCEMENT_LABEL, area_to_label(area)]
    label_args: list[str] = []
    for label in labels:
        label_args.extend(["--label", label])
    url = _run_gh(
        [
            "issue",
            "create",
            "--title",
            title,
            "--body",
            body,
            *label_args,
        ]
    )
    entry = _issue_to_entry(_view_issue(_issue_number_from_url(url)))
    if not entry.get("id"):
        entry["id"] = enh_id
    if closed:
        number = entry.get("issue_number")
        if number:
            if pr_url:
                _run_gh(["issue", "comment", str(number), "--body", f"Shipped in {pr_url}"])
            _run_gh(["issue", "close", str(number)])
            entry["status"] = "done"
    return entry


def close_issue(raw_id: str, *, pr_url: str | None = None) -> bool:
    entry = get_issue(raw_id)
    if entry is None:
        return False
    number = entry.get("issue_number")
    if not number:
        return False

    completed_at = datetime.now(UTC).isoformat()
    pr = (pr_url or entry.get("pr_url") or "").strip()
    body = format_issue_body(
        enh_id=entry.get("id") or "",
        area=entry.get("area") or "other",
        description=entry.get("description") or "",
        pr_url=pr,
        completed_at=completed_at,
    )
    _run_gh(["issue", "edit", str(number), "--body", body])
    if pr:
        _run_gh(["issue", "comment", str(number), "--body", f"Shipped in {pr}"])
    _run_gh(["issue", "close", str(number)])
    return True


def ensure_labels() -> None:
    """Create backlog labels if missing (idempotent)."""
    try:
        existing_raw = _run_gh(["label", "list", "--json", "name"])
        existing = {item["name"] for item in json.loads(existing_raw)} if existing_raw else set()
    except GhError:
        existing = set()

    to_create: list[tuple[str, str, str]] = [
        (ENHANCEMENT_LABEL, "5319E7", "grocery_wizard enhancement backlog"),
        ("gw-area-ui", "1D76DB", "Enhancement area: UI"),
        ("gw-area-parser", "0E8A16", "Enhancement area: parser"),
        ("gw-area-shopping", "FBCA04", "Enhancement area: shopping"),
        ("gw-area-recipes", "D93F0B", "Enhancement area: recipes"),
        ("gw-area-cli", "BFDADC", "Enhancement area: CLI"),
        ("gw-area-other", "C5DEF5", "Enhancement area: other"),
    ]
    for name, color, description in to_create:
        if name in existing:
            continue
        with suppress(GhError):
            _run_gh(["label", "create", name, "--color", color, "--description", description])
