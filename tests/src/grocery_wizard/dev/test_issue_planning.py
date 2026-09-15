from src.grocery_wizard.dev.issue_planning import (
    classify_kind,
    infer_area,
    plan_from_items,
)


def test_classify_kind_bug_vs_enhancement() -> None:
    assert classify_kind("The parser crashes on unicode") == "bug"
    assert classify_kind("Add support for recurring items in UI") == "enhancement"


def test_infer_area_from_keywords() -> None:
    assert infer_area("Streamlit button layout") == "ui"
    assert infer_area("ingredient junk phrases") == "parser"
    assert infer_area("random idea") == "other"


def test_plan_merges_same_area_and_kind() -> None:
    planned = plan_from_items(
        [
            "UI: improve grocery list spacing",
            "UI: fix mobile layout on list step",
        ]
    )
    assert len(planned) == 1
    assert planned[0].kind == "enhancement"
    assert planned[0].area == "ui"
    assert len(planned[0].source_items) == 2


def test_plan_splits_different_areas() -> None:
    planned = plan_from_items(
        [
            "Parser drops amounts on split lines",
            "Pantry sync removes staples",
        ]
    )
    assert len(planned) == 2
    areas = {p.area for p in planned}
    assert areas == {"parser", "shopping"}


def test_plan_splits_bug_and_enhancement() -> None:
    planned = plan_from_items(
        [
            "Add NYT collection filter",
            "Grocery list is empty when plan has meals — broken",
        ]
    )
    kinds = {p.kind for p in planned}
    assert kinds == {"enhancement", "bug"}
    assert len(planned) == 2
