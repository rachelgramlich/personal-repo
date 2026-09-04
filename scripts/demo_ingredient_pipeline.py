#!/usr/bin/env python3
"""Demo ingredient parsing pipeline outputs for manual verification."""

from __future__ import annotations

from dataclasses import dataclass

from src.grocery_wizard.ingredients.parsed import (
    aggregate_amounts,
    clean_ingredient_line_for_storage,
    minimal_clean_for_storage,
    parse_amount,
    should_show_amount,
)
from src.grocery_wizard.shopping.grocery_list import format_grocery_item


@dataclass
class Example:
    label: str
    raw_lines: list[str]
    expected: str | None = None
    nyt: bool = False
    aggregate: bool = False


def process_line(raw: str, *, nyt: bool = False) -> dict:
    stored = minimal_clean_for_storage(raw) if nyt else clean_ingredient_line_for_storage(raw)
    name, amount = parse_amount(raw)
    show_amount = should_show_amount(amount, raw)
    if name == "garlic":
        grocery_amount = aggregate_amounts([amount], name=name)
    else:
        grocery_amount = amount if show_amount else None
    grocery_line = format_grocery_item(name, grocery_amount)
    return {
        "raw": raw,
        "stored": stored,
        "name": name,
        "amount": amount,
        "grocery_line": grocery_line,
        "grocery_amount": grocery_amount,
    }


def process_example(ex: Example) -> dict:
    rows = [process_line(line, nyt=ex.nyt) for line in ex.raw_lines]
    if ex.aggregate and len(rows) > 1:
        amounts = [r["amount"] for r in rows if r["name"]]
        names = [r["name"] for r in rows if r["name"]]
        display_name = names[0] if names else ""
        agg = aggregate_amounts(amounts, name=display_name)
        agg_line = format_grocery_item(display_name, agg)
    else:
        agg_line = None
    return {"label": ex.label, "expected": ex.expected, "rows": rows, "aggregate_line": agg_line}


EXAMPLES: list[Example] = [
    # --- Issue #21 hard cases ---
    Example(
        label="Lemon juice + zest + whole (issue #21)",
        raw_lines=[
            "juice of half a lemon",
            "zest of 1 lemon",
            "2 lemons",
        ],
        expected="3 lemons",
        aggregate=True,
    ),
    Example(
        label="Chicken thighs with weight parenthetical",
        raw_lines=[
            "10 boneless, skinless chicken thighs (2½ to 3 pounds)",
        ],
        expected="10 boneless, skinless chicken thighs",
    ),
    Example(
        label="Fresh ginger with prep",
        raw_lines=["1 tablespoon fresh ginger, peeled and grated"],
        expected="ginger",
    ),
    Example(
        label="Celery stalk range (or)",
        raw_lines=["4 large or 6 small celery stalks"],
        expected="6 celery stalks",
    ),
    Example(
        label="Optional sherry vinegar",
        raw_lines=["Optional: 1/2 cup sherry vinegar, more as needed"],
        expected="sherry vinegar",
    ),
    Example(
        label="Dual measure flour",
        raw_lines=["1 cup/110 grams all-purpose flour"],
        expected="flour",
    ),
    Example(
        label="Bare ingredient (chimichurri)",
        raw_lines=["chimichurri"],
        expected="chimichurri",
    ),
    # --- Additional diverse examples ---
    Example(
        label="NYT-style: minimal clean (structured line)",
        raw_lines=["2 tablespoons extra-virgin olive oil, plus more for drizzling"],
        nyt=True,
    ),
    Example(
        label="NYT-style: onion with prep kept",
        raw_lines=["1 medium yellow onion, finely diced"],
        nyt=True,
    ),
    Example(
        label="Volume-only olive oil",
        raw_lines=["2 tbsp olive oil, plus more for drizzling"],
    ),
    Example(
        label="Volume-only kosher salt",
        raw_lines=["kosher salt"],
    ),
    Example(
        label="Compound cans: diced tomatoes",
        raw_lines=["2 (15-ounce) cans diced tomatoes"],
    ),
    Example(
        label="Lemon variant aggregation (juice + 1 + zest)",
        raw_lines=[
            "juice of half a lemon",
            "1 lemon",
            "zest of 1 lemon",
        ],
        expected="3 lemons",
        aggregate=True,
    ),
    Example(
        label="Optional ground meat alternatives",
        raw_lines=["Optional: 1 lb ground chicken, turkey, or beef"],
    ),
    Example(
        label="Parenthetical substitution preserved",
        raw_lines=[
            "1 chicken bouillon cube (or substitute 2 cups chicken broth for the water bouillon)",
        ],
    ),
    Example(
        label="Garlic cloves with prep",
        raw_lines=["3 cloves garlic, minced"],
        expected="garlic",
    ),
    Example(
        label="Multi-recipe garlic aggregation",
        raw_lines=["3 cloves garlic, minced", "2 cloves garlic, smashed and peeled"],
        expected="garlic",
        aggregate=True,
    ),
    Example(
        label="Many garlic cloves aggregation",
        raw_lines=["6 cloves garlic, minced", "6 cloves garlic, smashed and peeled"],
        expected="2 garlic",
        aggregate=True,
    ),
    Example(
        label="Explicit head garlic",
        raw_lines=["1 head garlic"],
        expected="1 garlic",
    ),
    Example(
        label="Mixed clove and head garlic",
        raw_lines=["3 cloves garlic, minced", "1 head garlic"],
        expected="1 garlic",
        aggregate=True,
    ),
    Example(
        label="Many cloves plus explicit head garlic",
        raw_lines=["12 cloves garlic, minced", "1 head garlic"],
        expected="2 garlic",
        aggregate=True,
    ),
    Example(
        label="Multi-recipe onion aggregation",
        raw_lines=["1 medium onion, diced", "2 small yellow onions, sliced"],
        aggregate=True,
    ),
    Example(
        label="Weight-only chicken breast",
        raw_lines=["1 lb boneless skinless chicken breast"],
    ),
    Example(
        label="Crushed red pepper (preserved product)",
        raw_lines=["Crushed red pepper"],
    ),
    Example(
        label="To taste preserved raw",
        raw_lines=["Salt and pepper to taste"],
    ),
    Example(
        label="Frozen spinach with oz",
        raw_lines=["10 oz frozen spinach"],
    ),
]


def main() -> None:
    print("=" * 72)
    print("INGREDIENT PARSING PIPELINE DEMO")
    print("=" * 72)

    summary_rows: list[tuple[str, str, str, str, str, str]] = []

    hard_labels = {
        "Lemon juice + zest + whole (issue #21)",
        "Chicken thighs with weight parenthetical",
        "Fresh ginger with prep",
        "Celery stalk range (or)",
        "Optional sherry vinegar",
        "Dual measure flour",
        "Bare ingredient (chimichurri)",
    }

    hard_results: list[dict] = []
    other_results: list[dict] = []

    for ex in EXAMPLES:
        result = process_example(ex)
        if ex.label in hard_labels:
            hard_results.append(result)
        else:
            other_results.append(result)

        for row in result["rows"]:
            summary_rows.append(
                (
                    ex.label,
                    row["raw"],
                    row["stored"],
                    row["name"],
                    str(row["amount"]),
                    row["grocery_line"],
                )
            )
        if result["aggregate_line"]:
            summary_rows.append(
                (
                    f"{ex.label} [AGG]",
                    " + ".join(r["raw"] for r in result["rows"]),
                    " | ".join(r["stored"] for r in result["rows"]),
                    result["rows"][0]["name"],
                    " → ".join(str(r["amount"]) for r in result["rows"]),
                    result["aggregate_line"],
                )
            )

    def print_section(title: str, results: list[dict]) -> None:
        print(f"\n{'#' * 72}")
        print(f"# {title}")
        print(f"{'#' * 72}")
        for result in results:
            print(f"\n## {result['label']}")
            if result["expected"]:
                print(f"   Expected: {result['expected']}")
            for i, row in enumerate(result["rows"], 1):
                prefix = f"  [{i}]" if len(result["rows"]) > 1 else " "
                print(f"{prefix} Raw:     {row['raw']!r}")
                print(f"{prefix} Stored:  {row['stored']!r}")
                print(f"{prefix} Parsed:  name={row['name']!r}, amount={row['amount']!r}")
                print(f"{prefix} Grocery: {row['grocery_line']!r}")
            if result["aggregate_line"]:
                print(f"  AGGREGATED grocery line: {result['aggregate_line']!r}")

    print_section("ISSUE #21 HARD CASES", hard_results)
    print_section("ADDITIONAL EXAMPLES", other_results)

    print(f"\n{'=' * 72}")
    print("SUMMARY TABLE (tab-separated for copy/paste)")
    print(f"{'=' * 72}")
    print("Label\tRaw\tStored\tName\tAmount\tGrocery")
    for row in summary_rows:
        print("\t".join(row))


if __name__ == "__main__":
    main()
