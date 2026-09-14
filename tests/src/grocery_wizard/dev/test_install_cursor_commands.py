from pathlib import Path

from src.grocery_wizard.dev.cursor_command_templates import CURSOR_COMMAND_FILES
from src.grocery_wizard.dev.install_cursor_commands import install_cursor_commands


def test_install_cursor_commands_writes_templates(tmp_path: Path) -> None:
    root = install_cursor_commands(repo_root=tmp_path)
    commands_dir = root / ".cursor" / "commands"

    assert commands_dir.is_dir()
    for filename in CURSOR_COMMAND_FILES:
        path = commands_dir / filename
        assert path.is_file()
        assert path.read_text(encoding="utf-8") == CURSOR_COMMAND_FILES[filename]
