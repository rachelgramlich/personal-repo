import pytest

from src.grocery_wizard.dev.enhancement_github import (
    format_backlog_title,
    format_issue_body,
    is_backlog_issue,
    link_issue_pr,
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


def test_link_issue_pr_edits_and_comments_without_close(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_gh(args: list[str], *, input_text: str | None = None) -> str:
        del input_text
        calls.append(args)
        if args[:3] == ["issue", "view", "7"]:
            return (
                '{"number":7,"title":"[Grocery Wizard] Link test","body":"desc\\n\\n---\\n**Area:** ui",'
                '"state":"OPEN","createdAt":"2026-01-01T00:00:00Z","url":"https://github.com/o/r/issues/7",'
                '"labels":[]}'
            )
        return ""

    monkeypatch.setattr(
        "src.grocery_wizard.dev.enhancement_github._run_gh",
        fake_run_gh,
    )
    assert link_issue_pr("7", pr_url="https://github.com/o/r/pull/99")
    assert len(calls) == 3
    assert calls[0][:3] == ["issue", "view", "7"]
    assert calls[1][:3] == ["issue", "edit", "7"]
    assert calls[2][:3] == ["issue", "comment", "7"]
    assert not any(c[:2] == ["issue", "close"] for c in calls)
