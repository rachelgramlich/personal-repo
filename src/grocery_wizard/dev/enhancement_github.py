"""GitHub Issues backend for the grocery_wizard enhancement backlog."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from typing import Any

BACKLOG_LABEL = "grocery-wizard"
BACKLOG_TITLE_PREFIX = "[Grocery Wizard] "
AREA_LABEL_PREFIX = "gw-area-"
_BACKLOG_SEARCH_QUERY = f'label:{BACKLOG_LABEL} OR "Grocery Wizard" in:title'

_AREA_BODY_RE = re.compile(r"\*\*Area:\*\*\s*(\w+)", re.IGNORECASE)
_AREA_MARKDOWN_RE = re.compile(
    r"^##\s*Area\s*\n+\s*`?(\w+)`?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_AREA_FORM_RE = re.compile(r"###\s*Area\s*\n+\s*(\w+)", re.IGNORECASE)
_FORM_SECTION_RE = re.compile(
    r"###\s*(?P<heading>[^\n]+)\s*\n+(?P<body>.*?)(?=\n###|\n---|\Z)",
    re.DOTALL | re.IGNORECASE,
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


def strip_backlog_title_prefix(title: str) -> str:
    return _BACKLOG_TITLE_PREFIX_RE.sub("", title.strip(), count=1).strip()


def normalize_backlog_title(title: str) -> str:
    """Return a clean backlog title (no legacy ``[Grocery Wizard]`` prefix)."""
    return strip_backlog_title_prefix(title)


def _issue_label_names(issue: dict[str, Any]) -> list[str]:
    labels = issue.get("labels") or []
    names: list[str] = []
    for label in labels:
        if isinstance(label, dict):
            names.append(label.get("name") or "")
        else:
            names.append(str(label))
    return names


def _legacy_title_backlog(title: str) -> bool:
    return "grocery wizard" in (title or "").lower()


def is_backlog_issue(issue: dict[str, Any]) -> bool:
    if BACKLOG_LABEL in _issue_label_names(issue):
        return True
    return _legacy_title_backlog(issue.get("title") or "")


def ensure_backlog_label() -> None:
    """Create the ``grocery-wizard`` label on the repo if it is missing."""
    raw = _run_gh(["label", "list", "--json", "name"])
    names = {entry.get("name") for entry in json.loads(raw or "[]") if isinstance(entry, dict)}
    if BACKLOG_LABEL in names:
        return
    _run_gh(
        [
            "label",
            "create",
            BACKLOG_LABEL,
            "--description",
            "Grocery Wizard enhancement backlog",
            "--color",
            "1D76DB",
        ]
    )


def _backlog_labels_for_area(area: str) -> list[str]:
    return [BACKLOG_LABEL, area_to_label(area)]


def _form_section(body: str, heading_prefix: str) -> str:
    prefix = heading_prefix.lower()
    for match in _FORM_SECTION_RE.finditer(body or ""):
        heading = (match.group("heading") or "").strip().lower()
        if heading.startswith(prefix):
            return (match.group("body") or "").strip()
    return ""


def format_feature_issue_body(
    *,
    area: str,
    description: str,
    expected_behavior: str = "",
    pr_url: str = "",
    completed_at: str = "",
) -> str:
    """Body aligned with ``.github/ISSUE_TEMPLATE/grocery_wizard_enhancement.yml``."""
    desc = (description or "").strip()
    expected = (expected_behavior or "").strip()
    parts: list[str] = [f"### Description\n\n{desc}"]
    if expected:
        parts.append(f"### Expected behavior & manual test hints\n\n{expected}")
    parts.append(f"### Area\n\n{area}")
    text = "\n\n".join(parts)
    meta: list[str] = []
    if pr_url:
        meta.append(f"**PR:** {pr_url.strip()}")
    if completed_at:
        meta.append(f"**Completed:** {completed_at}")
    if meta:
        text = f"{text}\n\n---\n" + "\n".join(meta)
    return text


def format_issue_body(
    *,
    area: str,
    description: str,
    expected_behavior: str = "",
    pr_url: str = "",
    completed_at: str = "",
) -> str:
    return format_feature_issue_body(
        area=area,
        description=description,
        expected_behavior=expected_behavior,
        pr_url=pr_url,
        completed_at=completed_at,
    )


def format_bug_issue_body(
    *,
    description: str,
    repro: str,
    actual: str,
    expected: str,
    context: str = "",
) -> str:
    """Body aligned with ``.github/ISSUE_TEMPLATE/bug_report.yml``."""
    parts = [
        f"### Describe the bug\n\n{(description or '').strip()}",
        f"### Steps to reproduce\n\n{(repro or '').strip()}",
        f"### Actual behavior\n\n{(actual or '').strip()}",
        f"### Expected behavior\n\n{(expected or '').strip()}",
    ]
    extra = (context or "").strip()
    if extra:
        parts.append(f"### Additional context\n\n{extra}")
    return "\n\n".join(parts)


def _legacy_description_from_body(text: str) -> str:
    if "\n---\n" in text:
        return text.split("\n---\n", 1)[0].strip()
    m = re.search(r"\n##\s*Area\s*\n", text, re.IGNORECASE)
    if m:
        return text[: m.start()].strip()
    return text.strip()


def _agent_description(description: str, expected_behavior: str) -> str:
    desc = (description or "").strip()
    expected = (expected_behavior or "").strip()
    if not expected:
        return desc
    if not desc:
        return f"**Expected behavior & manual test hints:**\n{expected}"
    return f"{desc}\n\n**Expected behavior & manual test hints:**\n{expected}"


def parse_issue_body(body: str) -> dict[str, str]:
    text = body or ""
    area_match = (
        _AREA_BODY_RE.search(text)
        or _AREA_MARKDOWN_RE.search(text)
        or _AREA_FORM_RE.search(text)
    )
    pr_match = _PR_BODY_RE.search(text)
    description = _form_section(text, "description") or _form_section(text, "describe the bug")
    expected_behavior = _form_section(text, "expected behavior & manual test hints")
    if not description and "###" not in text:
        description = _legacy_description_from_body(text)
    return {
        "description": description,
        "expected_behavior": expected_behavior,
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
    agent_desc = _agent_description(
        parsed.get("description") or "",
        parsed.get("expected_behavior") or "",
    )
    return {
        "id": issue_id,
        "issue_number": number,
        "issue_url": issue.get("url") or "",
        "timestamp": issue.get("createdAt") or "",
        "status": "open" if state == "OPEN" else "done",
        "title": strip_backlog_title_prefix(raw_title),
        "description": agent_desc,
        "area": area,
        "tags": [],
        "pr_url": parsed.get("pr_url") or "",
    }


def _search_backlog_issues(*, state: str) -> list[dict[str, Any]]:
    """state: ``open`` or ``closed`` (``gh issue list --search`` on current repo)."""
    if state not in {"open", "closed"}:
        raise ValueError(f"unsupported search state {state!r}")
    raw = _run_gh(
        [
            "issue",
            "list",
            "--search",
            _BACKLOG_SEARCH_QUERY,
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
    expected_behavior: str = "",
    closed: bool = False,
    pr_url: str = "",
    completed_at: str = "",
) -> dict[str, Any]:
    body = format_feature_issue_body(
        area=area,
        description=description,
        expected_behavior=expected_behavior,
        pr_url=pr_url,
        completed_at=completed_at,
    )
    ensure_backlog_label()
    issue_title = normalize_backlog_title(title)
    create_args = [
        "issue",
        "create",
        "--title",
        issue_title,
        "--body",
        body,
    ]
    for label in _backlog_labels_for_area(area):
        create_args.extend(["--label", label])
    url = _run_gh(create_args)
    entry = _issue_to_entry(_view_issue(_issue_number_from_url(url)))
    if closed:
        number = entry.get("issue_number")
        if number:
            if pr_url:
                _run_gh(["issue", "comment", str(number), "--body", f"Shipped in {pr_url}"])
            _run_gh(["issue", "close", str(number)])
            entry["status"] = "done"
    return entry


def create_bug_issue(
    title: str,
    *,
    description: str,
    repro: str,
    actual: str,
    expected: str,
    context: str = "",
) -> dict[str, Any]:
    body = format_bug_issue_body(
        description=description,
        repro=repro,
        actual=actual,
        expected=expected,
        context=context,
    )
    issue_title = title.strip()
    url = _run_gh(
        [
            "issue",
            "create",
            "--title",
            issue_title,
            "--body",
            body,
            "--label",
            "bug",
        ]
    )
    return json.loads(
        _run_gh(
            [
                "issue",
                "view",
                _issue_number_from_url(url),
                "--json",
                "number,title,url",
            ]
        )
    )


def close_issue(raw_id: str, *, pr_url: str | None = None) -> bool:
    """Close a backlog issue via ``gh`` (``dev close-enhancement``; JSONL import when done)."""
    entry = get_issue(raw_id)
    if entry is None:
        return False
    number = entry.get("issue_number")
    if not number:
        return False

    completed_at = datetime.now(UTC).isoformat()
    pr = (pr_url or entry.get("pr_url") or "").strip()
    raw = _view_issue(number)
    parsed = parse_issue_body(raw.get("body") or "")
    body = format_feature_issue_body(
        area=entry.get("area") or "other",
        description=parsed.get("description") or "",
        expected_behavior=parsed.get("expected_behavior") or "",
        pr_url=pr,
        completed_at=completed_at,
    )
    _run_gh(["issue", "edit", str(number), "--body", body])
    if pr:
        _run_gh(["issue", "comment", str(number), "--body", f"Shipped in {pr}"])
    _run_gh(["issue", "close", str(number)])
    return True


def backfill_backlog_labels(*, strip_title_prefix: bool = False) -> list[dict[str, Any]]:
    """One-time migration: label legacy title-matched issues; optionally strip title prefix."""
    ensure_backlog_label()
    updated: list[dict[str, Any]] = []
    for state in ("open", "closed"):
        raw = _run_gh(
            [
                "issue",
                "list",
                "--search",
                '"Grocery Wizard" in:title',
                "--state",
                state,
                "--limit",
                "100",
                "--json",
                "number,title,url,labels",
            ]
        )
        if not raw:
            continue
        for issue in json.loads(raw):
            if not _legacy_title_backlog(issue.get("title") or ""):
                continue
            number = issue.get("number")
            if not isinstance(number, int):
                continue
            label_names = _issue_label_names(issue)
            actions: list[str] = []
            if BACKLOG_LABEL not in label_names:
                _run_gh(["issue", "edit", str(number), "--add-label", BACKLOG_LABEL])
                actions.append("labeled")
            if strip_title_prefix:
                raw_title = issue.get("title") or ""
                clean = normalize_backlog_title(raw_title)
                if clean and clean != raw_title:
                    _run_gh(["issue", "edit", str(number), "--title", clean])
                    actions.append("title")
            if actions:
                updated.append(
                    {
                        "number": number,
                        "url": issue.get("url") or "",
                        "actions": actions,
                    }
                )
    return updated


def comment_on_pr(pr_url: str, body: str) -> None:
    text = body.strip()
    if not text:
        raise ValueError("comment body must be non-empty")
    _run_gh(["pr", "comment", pr_url.strip(), "--body", text])
