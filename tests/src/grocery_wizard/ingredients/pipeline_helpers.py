"""Shared helpers for ingredient pipeline integration tests."""

from __future__ import annotations

from dataclasses import dataclass

from src.grocery_wizard.ingredients.normalize import (
    aggregate_amounts,
    clean_ingredient_line_for_storage,
    parse_amount,
    should_show_amount,
)
from src.grocery_wizard.ingredients.parsed import minimal_clean_for_storage
from src.grocery_wizard.shopping.grocery_list import format_grocery_item


@dataclass(frozen=True)
class ProcessedIngredientLine:
    raw: str
    stored: str
    name: str
    amount: str | None
    grocery_line: str
    grocery_amount: str | None


def process_ingredient_line(raw: str, *, nyt: bool = False) -> ProcessedIngredientLine:
    """Run one ingredient line through storage, parse, and grocery formatting."""
    stored = minimal_clean_for_storage(raw) if nyt else clean_ingredient_line_for_storage(raw)
    name, amount = parse_amount(raw)
    show_amount = should_show_amount(amount, raw)
    if name == "garlic":
        grocery_amount = aggregate_amounts([amount], name=name)
    else:
        grocery_amount = amount if show_amount else None
    grocery_line = format_grocery_item(name, grocery_amount)
    return ProcessedIngredientLine(
        raw=raw,
        stored=stored,
        name=name,
        amount=amount,
        grocery_line=grocery_line,
        grocery_amount=grocery_amount,
    )


def aggregate_pipeline_lines(lines: list[ProcessedIngredientLine]) -> str | None:
    """Aggregate parsed amounts across lines and format a grocery item."""
    amounts = [line.amount for line in lines if line.name]
    names = [line.name for line in lines if line.name]
    display_name = names[0] if names else ""
    agg = aggregate_amounts(amounts, name=display_name)
    return format_grocery_item(display_name, agg)
