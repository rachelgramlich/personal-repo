"""Audit Notion recipe ingredient quality."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.grocery_wizard.notion import Recipe
from src.grocery_wizard.scraper import _has_merge_artifacts, _looks_fragmented

_BR_SPLIT = re.compile(r"<br\s*/?>", re.IGNORECASE)


@dataclass
class AuditReport:
    empty: list[str] = field(default_factory=list)
    no_link: list[str] = field(default_factory=list)
    suspicious: list[str] = field(default_factory=list)
    ok: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.empty) + len(self.no_link) + len(self.suspicious) + len(self.ok)


def split_ingredient_lines(text: str) -> list[str]:
    if not text or not text.strip():
        return []

    normalized = _BR_SPLIT.sub("\n", text)
    lines: list[str] = []
    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        line = re.sub(r"^[▢•*]\s*", "", line)
        line = re.sub(r"^\\[ \\]\s*▢?", "", line).strip()
        if line:
            lines.append(line)
    return lines


def looks_suspicious_ingredients(text: str) -> bool:
    lines = split_ingredient_lines(text)
    if not lines:
        return False
    return _looks_fragmented(lines) or _has_merge_artifacts(lines)


def audit_recipes(recipes: list[Recipe]) -> AuditReport:
    report = AuditReport()
    for recipe in recipes:
        name = recipe.name
        has_link = bool(recipe.link and recipe.link.strip())
        has_ingredients = bool(recipe.ingredients and recipe.ingredients.strip())

        if not has_link:
            report.no_link.append(name)
            if not has_ingredients:
                report.empty.append(name)
            continue

        if not has_ingredients:
            report.empty.append(name)
            continue

        if looks_suspicious_ingredients(recipe.ingredients):
            report.suspicious.append(name)
        else:
            report.ok.append(name)

    return report


def format_audit_report(report: AuditReport) -> str:
    def _section(title: str, names: list[str]) -> list[str]:
        section = [f"{title} ({len(names)}):"]
        if names:
            section.extend(f"  - {name}" for name in sorted(names))
        else:
            section.append("  (none)")
        return section

    lines = [
        "Recipe ingredient audit",
        f"Total recipes: {report.total}",
        "",
        *_section("Empty ingredients", report.empty),
        "",
        *_section("No link", report.no_link),
        "",
        *_section("Suspicious / broken", report.suspicious),
        "",
        *_section("OK", report.ok),
        "",
        "Recommended next steps:",
    ]
    if report.empty:
        lines.append("  - Run: dev backfill-ingredients")
    if report.suspicious:
        lines.append("  - Run: dev reconcile-ingredients  (re-scrape broken recipes)")
    if report.no_link and not report.empty:
        lines.append("  - Add links or paste ingredients manually for no-link recipes")
    if not report.empty and not report.suspicious:
        lines.append("  - No sync needed unless you want to refresh populated recipes")

    return "\n".join(lines)
