from src.grocery_wizard.dev.enhancement_github import (
    BACKLOG_LABEL,
    format_bug_issue_body,
    format_feature_issue_body,
    format_issue_body,
    is_backlog_issue,
    normalize_backlog_title,
    parse_issue_body,
    strip_backlog_title_prefix,
)


def test_normalize_backlog_title_strips_legacy_prefix() -> None:
    assert normalize_backlog_title("My feature") == "My feature"
    assert normalize_backlog_title("[Grocery Wizard] Already") == "Already"


def test_is_backlog_issue_matches_label_or_legacy_title() -> None:
    assert is_backlog_issue({"title": "[Grocery Wizard] Pantry", "labels": []})
    assert is_backlog_issue({"title": "Pantry sync", "labels": [{"name": BACKLOG_LABEL}]})
    assert not is_backlog_issue({"title": "Random bug", "labels": [{"name": "bug"}]})


def test_strip_backlog_title_prefix() -> None:
    assert strip_backlog_title_prefix("[Grocery Wizard] Pantry sync") == "Pantry sync"


def test_format_and_parse_feature_issue_body_roundtrip() -> None:
    body = format_feature_issue_body(
        area="shopping",
        description="First paragraph.\n\nSecond paragraph.",
        expected_behavior="Surface: CLI\nSteps: 1. run …\nExpected: …",
        pr_url="https://github.com/o/r/pull/9",
        completed_at="2026-01-01T00:00:00+00:00",
    )
    parsed = parse_issue_body(body)
    assert parsed["area_from_body"] == "shopping"
    assert parsed["pr_url"] == "https://github.com/o/r/pull/9"
    assert "First paragraph." in parsed["description"]
    assert "Surface: CLI" in parsed["expected_behavior"]
    assert "Enhancement ID" not in body


def test_format_issue_body_alias_matches_feature() -> None:
    body = format_issue_body(area="ui", description="Desc", expected_behavior="Steps")
    assert "### Description" in body
    assert "### Expected behavior" in body
    assert "### Area" in body


def test_format_and_parse_bug_issue_body() -> None:
    body = format_bug_issue_body(
        description="Pantry sync fails",
        repro="1. Open app\n2. Sync",
        actual="Empty list",
        expected="Items remain",
        context="Streamlit 1.x",
    )
    parsed = parse_issue_body(body)
    assert parsed["description"] == "Pantry sync fails"
    assert "1. Open app" in body
    assert "Streamlit" in body
