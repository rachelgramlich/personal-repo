"""Write Cursor slash-command files into the gitignored .cursor/commands/ directory."""

from __future__ import annotations

from pathlib import Path

from src.grocery_wizard.config import CONFIG_DIR
from src.grocery_wizard.dev.cursor_command_templates import CURSOR_COMMAND_FILES

REPO_ROOT = CONFIG_DIR.parent.parent.parent


def install_cursor_commands(repo_root: Path | None = None) -> Path:
    """Create .cursor/commands/ under repo_root and write embedded command templates."""
    root = (repo_root or REPO_ROOT).resolve()
    commands_dir = root / ".cursor" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in CURSOR_COMMAND_FILES.items():
        path = commands_dir / filename
        path.write_text(content, encoding="utf-8")

    return root
