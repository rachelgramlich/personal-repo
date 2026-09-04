"""End-to-end ingredient pipeline tests: ingest → storage → parse → grocery."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.src.grocery_wizard.ingredients.pipeline_helpers import (
    aggregate_pipeline_lines,
    process_ingredient_line,
)

if TYPE_CHECKING:
    from typing import Any


def test_pipeline_single_line_case(single_line_pipeline_case: dict[str, Any]) -> None:
    """Each single-line case flows from raw input to stored text and grocery output."""
    case = single_line_pipeline_case
    row = process_ingredient_line(case["raw_line"], nyt=case.get("nyt", False))

    if "expect_stored" in case:
        assert row.stored == case["expect_stored"]
    if "expect_grocery" in case:
        assert row.grocery_line == case["expect_grocery"]


def test_pipeline_aggregate_case(aggregate_pipeline_case: dict[str, Any]) -> None:
    """Multi-line cases aggregate parsed amounts into one grocery item."""
    case = aggregate_pipeline_case
    rows = [process_ingredient_line(raw, nyt=case.get("nyt", False)) for raw in case["raw_lines"]]
    assert aggregate_pipeline_lines(rows) == case["expect_aggregate_grocery"]


def test_issue_21_hard_cases(pipeline_cases: list[dict[str, Any]]) -> None:
    """Issue #21 hard cases remain covered as an explicit group."""
    hard_cases = [case for case in pipeline_cases if case.get("issue_21")]
    assert len(hard_cases) == 7

    for case in hard_cases:
        if case.get("aggregate"):
            rows = [process_ingredient_line(raw) for raw in case["raw_lines"]]
            assert aggregate_pipeline_lines(rows) == case["expect_aggregate_grocery"]
        else:
            row = process_ingredient_line(case["raw_line"])
            if "expect_stored" in case:
                assert row.stored == case["expect_stored"]
            if "expect_grocery" in case:
                assert row.grocery_line == case["expect_grocery"]
