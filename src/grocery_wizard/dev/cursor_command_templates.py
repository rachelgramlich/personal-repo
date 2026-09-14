"""Embedded Cursor slash-command templates (installed via dev install-cursor-commands)."""

# ruff: noqa: E501

from __future__ import annotations

from src.grocery_wizard.config import CONFIG_DIR

REPO_ROOT = CONFIG_DIR.parent.parent.parent
_COMMANDS_DIR = REPO_ROOT / ".cursor" / "commands"

_WORK_ALL_ENHANCEMENTS = """# Work all enhancements (spawn workers)

Orchestrate **one worker per open backlog item**. Do not implement the enhancements yourself in this chat — only coordinate parallel workers.

## Context

- Backlog: GitHub Issues with the **`grocery-wizard`** label.
- Spawn specs: `uv run python -m src.grocery_wizard dev spawn-enhancement-workers --json`

## Your task

1. Run:

```bash
uv run python -m src.grocery_wizard dev spawn-enhancement-workers --json
```

2. If the JSON array is empty, say the backlog has no open items and stop.

3. For **each** object in the array, start a worker **in parallel** (as many concurrent workers as the environment allows):

   - **Cloud Agent (preferred on desktop):** start a new Cloud Agent on this repo with `agent_message` as the first message (or paste the full `prompt` field).
   - **In-agent subagents:** launch a Task with `subagent_type=best-of-n-runner` and set the task description to `"<id>: <title>"`. Pass the full `prompt` string as the task instructions.

4. After launching, summarize for the user: enhancement ID, GitHub issue #, title, branch, and how each worker was started (URL if known).

5. Do **not** close backlog issues from the orchestrator chat — each worker opens a PR with `Closes #N` and handles manual verification when shipped.

Optional: reinstall slash commands after pulling:

```bash
uv run python -m src.grocery_wizard dev install-cursor-commands
```
"""


def _load_cursor_command_files() -> dict[str, str]:
    files: dict[str, str] = {}
    if _COMMANDS_DIR.is_dir():
        for path in sorted(_COMMANDS_DIR.glob("*.md")):
            files[path.name] = path.read_text(encoding="utf-8")
    if "work-all-enhancements.md" not in files:
        files["work-all-enhancements.md"] = _WORK_ALL_ENHANCEMENTS
    return files


CURSOR_COMMAND_FILES: dict[str, str] = _load_cursor_command_files()
