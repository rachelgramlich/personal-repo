"""Tests for store aisle classification and sorting."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.grocery_wizard.shopping.store_aisles import (
    classify_aisle,
    group_grocery_items_by_aisle,
    load_store_aisles,
    parse_store_aisles_file,
    sort_grocery_items,
)


def test_parse_store_aisles_file_reads_sections_and_keywords(tmp_path: Path) -> None:
    path = tmp_path / "store_aisles.txt"
    path.write_text(
        "\n".join(
            [
                "# --- produce: Fresh stuff ---",
                "onion",
                "garlic",
                "",
                "# --- other: Other ---",
                "# catch-all",
            ]
        ),
        encoding="utf-8",
    )

    config = parse_store_aisles_file(path)

    assert config.aisle_order == ("produce", "other")
    assert config.aisle_labels["produce"] == "Fresh stuff"
    assert config.aisle_keywords["produce"] == ("onion", "garlic")


def test_load_store_aisles_uses_committed_config() -> None:
    config = load_store_aisles()
    assert "produce" in config.aisle_order
    assert config.aisle_labels["produce"] == "Produce"
    assert "onion" in config.aisle_keywords["produce"]


@pytest.mark.parametrize(
    ("item", "expected_aisle"),
    [
        ("1 lb chicken breast", "other"),
        ("onions", "produce"),
        ("3 cloves garlic", "produce"),
        ("2 cans white beans", "dry goods"),
        ("1 lb spaghetti", "dry goods"),
        ("eggs", "dairy/eggs"),
        ("2 eggs", "dairy/eggs"),
        ("shredded cheddar", "refrigerated"),
        ("frozen peas", "frozen"),
        ("coffee beans", "coffee"),
        ("almonds", "nuts/dried fruit"),
        ("potato chips", "snacks"),
        ("all-purpose flour", "baking"),
        ("sourdough bread", "bakery"),
        ("la croix", "canned drinks"),
    ],
)
def test_classify_aisle(item: str, expected_aisle: str) -> None:
    assert classify_aisle(item) == expected_aisle


def test_sort_grocery_items_follows_store_walk_order() -> None:
    items = [
        "2 cans white beans",
        "onions",
        "eggs",
        "1 lb chicken breast",
        "shredded cheddar",
        "frozen peas",
    ]
    sorted_items = sort_grocery_items(items)

    produce_index = sorted_items.index("onions")
    refrigerated_index = sorted_items.index("shredded cheddar")
    dairy_index = sorted_items.index("eggs")
    dry_goods_index = sorted_items.index("2 cans white beans")
    frozen_index = sorted_items.index("frozen peas")
    other_index = sorted_items.index("1 lb chicken breast")

    assert produce_index < refrigerated_index < dairy_index < dry_goods_index < frozen_index
    assert other_index > frozen_index


def test_group_grocery_items_by_aisle_omits_empty_aisles() -> None:
    items = ["onions", "eggs", "2 cans white beans"]
    groups = group_grocery_items_by_aisle(items)

    assert [aisle for aisle, _ in groups] == ["produce", "dairy/eggs", "dry goods"]
    assert groups[0][1] == ["onions"]
    assert groups[1][1] == ["eggs"]
    assert groups[2][1] == ["2 cans white beans"]


def test_sort_grocery_items_is_stable_within_aisle() -> None:
    items = ["zucchini", "apples", "onions"]
    assert sort_grocery_items(items) == ["apples", "onions", "zucchini"]


def test_aisle_order_has_other_last() -> None:
    config = load_store_aisles()
    assert config.aisle_order[-1] == "other"
