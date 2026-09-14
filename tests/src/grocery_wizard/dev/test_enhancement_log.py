from pathlib import Path

from src.grocery_wizard.dev.enhancement_log import (
    add_enhancement,
    complete_enhancement,
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


def test_complete_enhancement_stores_pr_url(tmp_path: Path) -> None:
    path = tmp_path / "enhancements.jsonl"
    eid = add_enhancement("Done item", path=path)
    assert complete_enhancement(eid, pr_url="https://github.com/o/r/pull/1", path=path)
    entry = get_enhancement(eid, path=path)
    assert entry is not None
    assert entry["status"] == "done"
    assert entry["pr_url"] == "https://github.com/o/r/pull/1"
    assert entry.get("completed_at")
