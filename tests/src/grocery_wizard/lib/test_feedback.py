"""Tests for CLI feedback collection and persistence."""

from __future__ import annotations

import json

from src.grocery_wizard.lib.feedback import (
    append_feedback,
    format_feedback_list,
    list_feedback,
    load_feedback,
    prompt_for_feedback,
)


def test_load_feedback_returns_empty_when_missing(tmp_path) -> None:
    path = tmp_path / "feedback.json"
    assert load_feedback(path) == []


def test_append_feedback_creates_file(tmp_path) -> None:
    path = tmp_path / "feedback.json"
    append_feedback("plan-recipes", "Great suggestions", path=path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["command"] == "plan-recipes"
    assert data[0]["feedback"] == "Great suggestions"
    assert "timestamp" in data[0]


def test_append_feedback_appends_to_existing(tmp_path) -> None:
    path = tmp_path / "feedback.json"
    append_feedback("plan-recipes", "First note", path=path)
    append_feedback("create-grocery-list", "Second note", path=path)

    entries = load_feedback(path)
    assert len(entries) == 2
    assert entries[0]["feedback"] == "First note"
    assert entries[1]["feedback"] == "Second note"


def test_load_feedback_warns_on_corrupt_json(tmp_path, capsys) -> None:
    path = tmp_path / "feedback.json"
    path.write_text("not json", encoding="utf-8")

    assert load_feedback(path) == []
    err = capsys.readouterr().err
    assert "Warning" in err
    assert "empty feedback log" in err


def test_load_feedback_warns_when_not_array(tmp_path, capsys) -> None:
    path = tmp_path / "feedback.json"
    path.write_text('{"feedback": "oops"}', encoding="utf-8")

    assert load_feedback(path) == []
    err = capsys.readouterr().err
    assert "not a JSON array" in err


def test_prompt_for_feedback_skips_empty_input(tmp_path) -> None:
    path = tmp_path / "feedback.json"
    prompt_for_feedback("edit-pantry", prompt_fn=lambda _: "", path=path)
    assert not path.exists()


def test_prompt_for_feedback_appends_on_input(tmp_path) -> None:
    path = tmp_path / "feedback.json"
    prompt_for_feedback(
        "add-recipe",
        prompt_fn=lambda _: "  URL parsing was slow  ",
        path=path,
    )

    entries = load_feedback(path)
    assert len(entries) == 1
    assert entries[0]["command"] == "add-recipe"
    assert entries[0]["feedback"] == "URL parsing was slow"


def test_prompt_for_feedback_skips_on_keyboard_interrupt(tmp_path) -> None:
    path = tmp_path / "feedback.json"

    def raise_interrupt(_: str) -> str:
        raise KeyboardInterrupt

    prompt_for_feedback("plan-recipes", prompt_fn=raise_interrupt, path=path)
    assert not path.exists()


def test_format_feedback_list_newest_first() -> None:
    entries = [
        {"timestamp": "2026-01-01T00:00:00+00:00", "command": "a", "feedback": "old"},
        {"timestamp": "2026-01-02T00:00:00+00:00", "command": "b", "feedback": "new"},
    ]
    output = format_feedback_list(entries)
    lines = output.splitlines()
    assert len(lines) == 2
    assert "new" in lines[0]
    assert "old" in lines[1]


def test_list_feedback_no_entries(tmp_path) -> None:
    assert list_feedback(path=tmp_path / "feedback.json") == "No feedback yet."


def test_list_feedback_prints_entries(tmp_path) -> None:
    path = tmp_path / "feedback.json"
    append_feedback("plan-recipes", "Nice flow", path=path)
    output = list_feedback(path=path)
    assert "plan-recipes" in output
    assert "Nice flow" in output
