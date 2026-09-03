"""Shared CLI yes/no confirmation helpers."""

from __future__ import annotations

from collections.abc import Callable


def parse_yes_no(answer: str, *, default_yes: bool) -> bool:
    """Parse a y/n answer. Empty input uses the prompt default."""
    normalized = answer.strip().lower()
    if normalized in ("y", "yes"):
        return True
    if normalized in ("n", "no"):
        return False
    return default_yes


def confirm_yes_default(
    message: str,
    prompt_fn: Callable[[str], str] = input,
) -> bool:
    """[Y/n] — Enter = yes, only ``n`` declines."""
    answer = prompt_fn(f"{message} [Y/n]: ")
    return parse_yes_no(answer, default_yes=True)


def confirm_no_default(
    message: str,
    prompt_fn: Callable[[str], str] = input,
) -> bool:
    """[y/N] — Enter = no, only ``y`` affirms."""
    answer = prompt_fn(f"{message} [y/N]: ")
    return parse_yes_no(answer, default_yes=False)
