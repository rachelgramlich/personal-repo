from pathlib import Path

from src.grocery_wizard.dev.enhancement_log import (
    add_enhancement,
    format_agent_prompt,
    format_pr_title,
    get_enhancement,
)


def test_format_pr_title_prefixes_id(tmp_path: Path) -> None:
    path = tmp_path / "enhancements.jsonl"
    eid = add_enhancement("Short title", area="ui", path=path)
    entry = get_enhancement(eid, path=path)
    assert entry is not None
    assert format_pr_title(entry) == f"{eid}: Short title"


def test_format_pr_title_truncates_long_title(tmp_path: Path) -> None:
    path = tmp_path / "enhancements.jsonl"
    long_title = "x" * 300
    eid = add_enhancement(long_title, path=path)
    entry = get_enhancement(eid, path=path)
    assert entry is not None
    title = format_pr_title(entry)
    assert len(title) <= 256
    assert title.startswith(f"{eid}: ")


def test_format_pr_title_uses_issue_number() -> None:
    entry = {
        "id": "96",
        "issue_number": 96,
        "title": "Notion-backed pantry",
    }
    assert format_pr_title(entry) == "#96: Notion-backed pantry"


def test_format_agent_prompt_includes_uat_and_merge_close() -> None:
    prompt = format_agent_prompt(
        {
            "id": "42",
            "issue_number": 42,
            "title": "Test feature",
            "area": "ui",
            "description": "Do the thing",
        }
    )
    assert "Manual verification" in prompt
    assert "Closes #42" in prompt
    assert "record-manual-verification 42" in prompt
    assert "complete-enhancement" not in prompt
