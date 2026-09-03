"""Tests for CLI command names, deprecation messages, and help text."""

from __future__ import annotations

import argparse
from io import StringIO
from unittest.mock import patch

import pytest

from src.grocery_wizard.cli import main


@pytest.mark.parametrize(
    ("argv", "replacement"),
    [
        (["plan"], "plan-recipes"),
        (["grocery"], "create-grocery-list"),
        (["add"], "add-recipe"),
        (["pantry"], "edit-pantry"),
        (["dev", "backfill"], "backfill-ingredients"),
        (["dev", "reconcile"], "reconcile-ingredients"),
        (["dev", "refresh-all"], "refresh-all-ingredients"),
        (["dev", "audit"], "audit-recipes"),
        (["dev", "schema"], "show-schema"),
    ],
)
def test_deprecated_commands_print_replacement(argv: list[str], replacement: str) -> None:
    stderr = StringIO()
    with patch("sys.stderr", stderr):
        code = main(argv)
    assert code == 1
    output = stderr.getvalue()
    assert replacement in output
    assert "was removed" in output


def test_create_grocery_list_help_lists_new_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["create-grocery-list", "--help"])
    output = capsys.readouterr().out
    assert "--quiet" in output
    assert "--backfill-missing" in output
    assert "--include-staples" in output
    assert "--verbose" not in output
    assert "--sync-first" not in output
    assert "--include-pantry" not in output


def test_cmd_grocery_passes_new_flags() -> None:
    from src.grocery_wizard.cli import cmd_grocery

    args = argparse.Namespace(
        recipes="Soup,Salad",
        quiet=True,
        backfill_missing=True,
        include_staples=True,
    )
    with (
        patch("src.grocery_wizard.cli.load_config"),
        patch("src.grocery_wizard.cli.NotionRecipesDB"),
        patch("src.grocery_wizard.grocery_list.run_grocery_list") as run_mock,
    ):
        run_mock.return_value = 0
        assert cmd_grocery(args) == 0

    run_mock.assert_called_once()
    kwargs = run_mock.call_args.kwargs
    assert kwargs["recipe_names"] == ["Soup", "Salad"]
    assert kwargs["quiet"] is True
    assert kwargs["backfill_missing"] is True
    assert kwargs["exclude_pantry"] is False
