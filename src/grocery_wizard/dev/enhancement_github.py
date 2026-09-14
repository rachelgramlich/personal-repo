"""GitHub Issues backend for the grocery_wizard enhancement backlog."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from typing import Any

BACKLOG_TITLE_PREFIX = "[Grocery Wizard] "
AREA_LABEL_PREFIX = "gw-area-"

_AREA_BODY_RE = re.compile(r"\*\*Area:\*\*\s*(\w+)", re.IGNORECASE)
_AREA_MARKDOWN_RE = re.compile(
    r"^##\s*Area\s*\n+\s*`?(\w+)`?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_PR_BODY_RE = re.compile(r"\*\*PR:\*\*\s*(https?://\S+)", re.IGNORECASE)
_BACKLOG_TITLE_PREFIX_RE = re.compile(
    r"^(?:\[Grocery Wizard\]|Grocery Wizard:)\s*",
    re.IGNORECASE,
)


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


def format_backlog_title(title: str) -> str:
    """Ensure the issue title marks it as part of the Grocery Wizard backlog."""
    cleaned = title.strip()
    if "grocery wizard" in cleaned.lower():
        return cleaned
    return f"{BACKLOG_TITLE_PREFIX}{cleaned}"


def strip_backlog_title_prefix(title: str) -> str:
    return _BACKLOG_TITLE_PREFIX_RE.sub("", title.strip(), count=1).strip()


def is_backlog_issue(issue: dict[str, Any]) -> bool:
    return "grocery wizard" in (issue.get("title") or "").lower()


def format_issue_body(
    *,
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
    lines.append(f"**Area:** {area}")
    if pr_url:
        lines.append(f"**PR:** {pr_url.strip()}")
    if completed_at:
        lines.append(f"**Completed:** {completed_at}")
    return "\n".join(lines)


def _description_from_body(text: str) -> str:
    if "\n---\n" in text:
        return text.split("\n---\n", 1)[0].strip()
    m = re.search(r"\n##\s*Area\s*\n", text, re.IGNORECASE)
    if m:
        return text[: m.start()].strip()
    return text.strip()


def parse_issue_body(body: str) -> dict[str, str]:
    text = body or ""
    area_match = _AREA_BODY_RE.search(text) or _AREA_MARKDOWN_RE.search(text)
    pr_match = _PR_BODY_RE.search(text)
    description = _description_from_body(text)
    return {
        "description": description,
        "area_from_body": area_match.group(1).lower() if area_match else "",
        "pr_url": pr_match.group(1).strip() if pr_match else "",
    }


def _issue_to_entry(issue: dict[str, Any]) -> dict[str, Any]:
    labels = issue.get("labels") or []
    label_names = [lb.get("name", "") for lb in labels if isinstance(lb, dict)]
    parsed = parse_issue_body(issue.get("body") or "")
    state = (issue.get("state") or "OPEN").upper()
    area = parsed.get("area_from_body") or label_to_area(label_names)
    number = issue.get("number")
    issue_id = str(number) if number is not None else ""
    raw_title = issue.get("title") or ""
    return {
        "id": issue_id,
        "issue_number": number,
        "issue_url": issue.get("url") or "",
        "timestamp": issue.get("createdAt") or "",
        "status": "open" if state == "OPEN" else "done",
        "title": strip_backlog_title_prefix(raw_title),
        "description": parsed.get("description") or "",
        "area": area,
        "tags": [],
        "pr_url": parsed.get("pr_url") or "",
    }


def _search_backlog_issues(*, state: str) -> list[dict[str, Any]]:
    """state: ``open`` or ``closed`` (gh search issues)."""
    raw = _run_gh(
        [
            "search",
            "issues",
            "Grocery Wizard in:title",
            "--state",
            state,
            "--limit",
            "100",
            "--json",
            "number,title,body,state,createdAt,url,labels",
        ]
    )
    if not raw:
        return []
    issues = json.loads(raw)
    return [issue for issue in issues if is_backlog_issue(issue)]


def _fetch_issues(*, state: str) -> list[dict[str, Any]]:
    if state == "OPEN":
        return _search_backlog_issues(state="open")
    if state == "CLOSED":
        return _search_backlog_issues(state="closed")
    raise ValueError(f"unsupported state {state!r}")


def list_issues(*, include_closed: bool = False) -> list[dict[str, Any]]:
    if include_closed:
        open_issues = _fetch_issues(state="OPEN")
        closed_issues = _fetch_issues(state="CLOSED")
        issues = open_issues + closed_issues
        by_number: dict[int, dict[str, Any]] = {}
        for issue in issues:
            num = issue.get("number")
            if isinstance(num, int):
                by_number[num] = issue
        issues = list(by_number.values())
        issues.sort(key=lambda i: i.get("createdAt") or "", reverse=True)
        return [_issue_to_entry(i) for i in issues]
    issues = _fetch_issues(state="OPEN")
    issues.sort(key=lambda i: i.get("createdAt") or "", reverse=True)
    return [_issue_to_entry(i) for i in issues]


def _normalize_lookup_id(raw: str) -> str:
    return raw.strip().removeprefix("#")


def get_issue(raw_id: str) -> dict[str, Any] | None:
    lookup = _normalize_lookup_id(raw_id)
    if not lookup.isdigit():
        return None
    issue = _view_issue(lookup)
    if not is_backlog_issue(issue):
        return None
    return _issue_to_entry(issue)


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
    closed: bool = False,
    pr_url: str = "",
    completed_at: str = "",
) -> dict[str, Any]:
    body = format_issue_body(
        area=area,
        description=description,
        pr_url=pr_url,
        completed_at=completed_at,
    )
    issue_title = format_backlog_title(title)
    url = _run_gh(
        [
            "issue",
            "create",
            "--title",
            issue_title,
            "--body",
            body,
        ]
    )
    entry = _issue_to_entry(_view_issue(_issue_number_from_url(url)))
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
