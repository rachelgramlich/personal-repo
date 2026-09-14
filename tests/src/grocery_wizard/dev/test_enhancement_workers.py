import json
from pathlib import Path

from src.grocery_wizard.dev.enhancement_log import (
    add_enhancement,
    format_worker_spawn_message,
    list_worker_spawns,
)


def test_list_worker_spawns_open_only(tmp_path: Path) -> None:
    log = tmp_path / "enhancements.jsonl"
    add_enhancement("First idea", area="ui", path=log)
    add_enhancement("Second idea", area="parser", path=log)

    specs = list_worker_spawns(path=log)
    assert len(specs) == 2
    assert specs[0]["id"] == "enh_002"
    assert specs[0]["branch"] == "cursor/second-idea-21af"
    assert "enh_002" in specs[0]["agent_message"]
    assert specs[0]["prompt"].startswith("You are working in the grocery_wizard repo.")


def test_format_worker_spawn_message_includes_title() -> None:
    msg = format_worker_spawn_message({"id": "enh_001", "title": "Split copy UI"})
    assert msg == "/work-on-enhancement enh_001 — Split copy UI"


def test_spawn_cli_json(tmp_path: Path, monkeypatch) -> None:
    import argparse
    import io
    import sys

    from src.grocery_wizard.cli.main import cmd_dev_spawn_enhancement_workers
    from src.grocery_wizard.dev import enhancement_log

    log = tmp_path / "enhancements.jsonl"
    add_enhancement("CLI spawn test", path=log)
    monkeypatch.setattr(enhancement_log, "ENHANCEMENT_LOG_PATH", log)

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    args = argparse.Namespace(output_json=True)
    assert cmd_dev_spawn_enhancement_workers(args) == 0
    data = json.loads(buf.getvalue())
    assert len(data) == 1
    assert data[0]["id"] == "enh_001"
