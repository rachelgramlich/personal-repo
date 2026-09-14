import pytest

from src.grocery_wizard.dev.enhancement_github import (
    format_backlog_title,
    format_issue_body,
    is_backlog_issue,
    parse_issue_body,
    strip_backlog_title_prefix,
)


def test_format_backlog_title_adds_prefix() -> None:
    assert format_backlog_title("My feature") == "[Grocery Wizard] My feature"
    assert format_backlog_title("[Grocery Wizard] Already") == "[Grocery Wizard] Already"


def test_is_backlog_issue_matches_title() -> None:
    assert is_backlog_issue({"title": "[Grocery Wizard] Pantry"})
    assert not is_backlog_issue({"title": "Random bug"})


def test_strip_backlog_title_prefix() -> None:
    assert strip_backlog_title_prefix("[Grocery Wizard] Pantry sync") == "Pantry sync"


def test_format_and_parse_issue_body_roundtrip() -> None:
    body = format_issue_body(
        area="shopping",
        description="First paragraph.\n\nSecond paragraph.",
        pr_url="https://github.com/o/r/pull/9",
        completed_at="2026-01-01T00:00:00+00:00",
    )
    parsed = parse_issue_body(body)
    assert parsed["area_from_body"] == "shopping"
    assert parsed["pr_url"] == "https://github.com/o/r/pull/9"
    assert "First paragraph." in parsed["description"]
    assert "Enhancement ID" not in body
