"""Tests for shared CLI yes/no prompt helpers."""

from src.grocery_wizard.prompts import (
    confirm_no_default,
    confirm_yes_default,
    parse_yes_no,
)


def test_parse_yes_no_default_yes() -> None:
    assert parse_yes_no("", default_yes=True) is True
    assert parse_yes_no("y", default_yes=True) is True
    assert parse_yes_no("yes", default_yes=True) is True
    assert parse_yes_no("n", default_yes=True) is False
    assert parse_yes_no("no", default_yes=True) is False
    assert parse_yes_no("maybe", default_yes=True) is True


def test_parse_yes_no_default_no() -> None:
    assert parse_yes_no("", default_yes=False) is False
    assert parse_yes_no("y", default_yes=False) is True
    assert parse_yes_no("yes", default_yes=False) is True
    assert parse_yes_no("n", default_yes=False) is False
    assert parse_yes_no("no", default_yes=False) is False
    assert parse_yes_no("maybe", default_yes=False) is False


def test_confirm_yes_default_enter_accepts() -> None:
    prompts = iter(["", "n"])
    assert confirm_yes_default("Save plan?", prompt_fn=lambda _: next(prompts)) is True
    assert confirm_yes_default("Save plan?", prompt_fn=lambda _: next(prompts)) is False


def test_confirm_no_default_enter_declines() -> None:
    prompts = iter(["", "y"])
    assert confirm_no_default("Create recipe?", prompt_fn=lambda _: next(prompts)) is False
    assert confirm_no_default("Create recipe?", prompt_fn=lambda _: next(prompts)) is True
