"""Plan GitHub issues from one or more user notes (kind, area, grouping)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from src.grocery_wizard.dev.enhancement_log import VALID_AREAS

IssueKind = Literal["enhancement", "bug"]

_AREA_HINTS: dict[str, tuple[str, ...]] = {
    "ui": (
        "streamlit",
        "ui",
        "button",
        "page",
        "screen",
        "display",
        "wizard step",
        "sidebar",
    ),
    "parser": (
        "ingredient",
        "parse",
        "parser",
        "junk",
        "normalize",
        "pattern",
        "scrape line",
    ),
    "shopping": (
        "grocery",
        "pantry",
        "shopping",
        "aisle",
        "recurring",
        "staple",
        "list item",
    ),
    "recipes": (
        "recipe",
        "notion",
        "nyt",
        "meal plan",
        "week plan",
        "add-recipe",
    ),
    "cli": (
        "cli",
        "command",
        "dev ",
        "terminal",
        "slash command",
        "cursor command",
    ),
}

_BUG_HINTS = (
    "broken",
    "crash",
    "error",
    "fails",
    "failed",
    "failure",
    "wrong",
    "incorrect",
    "regression",
    "doesn't work",
    "does not work",
    "not working",
    "bug",
    "defect",
    "exception",
    "500",
    "blank screen",
    "empty when",
)

_ENH_HINTS = (
    "add ",
    "support ",
    "feature",
    "improve",
    "enhancement",
    "backlog",
    "would like",
    "wish ",
    "should have",
    "new ",
)


@dataclass
class PlannedIssue:
    kind: IssueKind
    area: str
    title: str
    source_items: list[str] = field(default_factory=list)
    description: str = ""
    expected_behavior: str = ""
    repro: str = ""
    actual: str = ""
    expected: str = ""
    context: str = ""
    audit: bool = False


def _normalize_area(area: str) -> str:
    cleaned = (area or "other").strip().lower()
    return cleaned if cleaned in VALID_AREAS else "other"


def classify_kind(text: str) -> IssueKind:
    lower = text.lower()
    bug_score = sum(1 for hint in _BUG_HINTS if hint in lower)
    enh_score = sum(1 for hint in _ENH_HINTS if hint in lower)
    if bug_score > enh_score:
        return "bug"
    if enh_score > bug_score:
        return "enhancement"
    if re.search(r"\b(fix|fixed|fixing)\b", lower) and bug_score > 0:
        return "bug"
    return "enhancement"


def infer_area(text: str) -> str:
    lower = text.lower()
    scores: dict[str, int] = {}
    for area, hints in _AREA_HINTS.items():
        scores[area] = sum(1 for hint in hints if hint in lower)
    best = max(scores.values()) if scores else 0
    if best == 0:
        return "other"
    for area, score in scores.items():
        if score == best:
            return area
    return "other"


def _title_from_text(text: str, *, max_len: int = 80) -> str:
    line = text.strip().splitlines()[0] if text.strip() else "Untitled"
    line = re.sub(r"\s+", " ", line).strip()
    if len(line) > max_len:
        line = line[: max_len - 1].rstrip() + "…"
    return line or "Untitled"


def _group_title(kind: IssueKind, area: str, items: list[str]) -> str:
    first = _title_from_text(items[0])
    if len(items) == 1:
        return first
    area_label = area if area != "other" else ("Bug bundle" if kind == "bug" else "Backlog bundle")
    return f"{area_label}: {first} (+ {len(items) - 1} related)"


def _enhancement_body(items: list[str]) -> tuple[str, str]:
    if len(items) == 1:
        text = items[0].strip()
        return text, "Surface, steps, and expected results (fill during implementation if needed)."
    bullets = "\n".join(f"- {item.strip()}" for item in items)
    description = (
        f"Grouped backlog items (same code area — intended to ship together):\n\n{bullets}"
    )
    expected = (
        "Manual verification for each bullet above; one PR may close this issue with "
        "`Closes #N` when all items are done."
    )
    return description, expected


def _bug_fields(items: list[str]) -> tuple[str, str, str, str, str]:
    combined = "\n\n".join(item.strip() for item in items)
    description = combined if len(items) > 1 else items[0].strip()
    repro = "See description (captured from user notes; refine steps if needed)."
    actual = "See description."
    expected = "Correct behavior as described in the issue (refine when fixing)."
    should_match = re.search(r"should\s+(.+?)(?:\.|$)", combined, re.IGNORECASE | re.DOTALL)
    if should_match:
        expected = should_match.group(1).strip().rstrip(".")
    return description, repro, actual, expected, ""


def plan_from_items(raw_items: list[str]) -> list[PlannedIssue]:
    """Merge notes that share kind + area; split when areas (or kind) differ."""
    cleaned = [item.strip() for item in raw_items if item and item.strip()]
    if not cleaned:
        return []

    buckets: dict[tuple[IssueKind, str], list[str]] = {}
    for text in cleaned:
        kind = classify_kind(text)
        area = _normalize_area(infer_area(text))
        buckets.setdefault((kind, area), []).append(text)

    planned: list[PlannedIssue] = []
    for (kind, area), items in sorted(buckets.items(), key=lambda x: (x[0][0], x[0][1])):
        title = _group_title(kind, area, items)
        if kind == "enhancement":
            description, expected_behavior = _enhancement_body(items)
            planned.append(
                PlannedIssue(
                    kind=kind,
                    area=area,
                    title=title,
                    source_items=list(items),
                    description=description,
                    expected_behavior=expected_behavior,
                )
            )
        else:
            description, repro, actual, expected, context = _bug_fields(items)
            planned.append(
                PlannedIssue(
                    kind=kind,
                    area=area,
                    title=title,
                    source_items=list(items),
                    description=description,
                    repro=repro,
                    actual=actual,
                    expected=expected,
                    context=context,
                )
            )
    return planned


def planned_issue_to_dict(issue: PlannedIssue) -> dict:
    return {
        "kind": issue.kind,
        "area": issue.area,
        "title": issue.title,
        "source_items": issue.source_items,
        "description": issue.description,
        "expected_behavior": issue.expected_behavior,
        "repro": issue.repro,
        "actual": issue.actual,
        "expected": issue.expected,
        "context": issue.context,
        "audit": issue.audit,
    }


def planned_issue_from_dict(data: dict) -> PlannedIssue:
    return PlannedIssue(
        kind=data.get("kind", "enhancement"),
        area=_normalize_area(data.get("area", "other")),
        title=(data.get("title") or "Untitled").strip(),
        source_items=list(data.get("source_items") or []),
        description=data.get("description") or "",
        expected_behavior=data.get("expected_behavior") or "",
        repro=data.get("repro") or "",
        actual=data.get("actual") or "",
        expected=data.get("expected") or "",
        context=data.get("context") or "",
        audit=bool(data.get("audit")),
    )
