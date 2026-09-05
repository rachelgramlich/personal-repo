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
    strip_checklist_prefix,
)


def test_parse_store_aisles_file_reads_sections_and_keywords(tmp_path: Path) -> None:
    path = tmp_path / "store_aisles.txt"
    path.write_text(
        "# --- produce: Fresh stuff ---\nonion\ngarlic\n\n# --- other: Other ---\n# catch-all",
        encoding="utf-8",
    )

    config = parse_store_aisles_file(path)

    assert config.aisle_order == ("produce", "other")
    assert config.aisle_labels["produce"] == "Fresh stuff"
    assert config.aisle_keywords["produce"] == ("onion", "garlic")


def test_load_store_aisles_uses_committed_config() -> None:
    config = load_store_aisles()
    assert config.aisle_order[0] == "flowers"
    assert config.aisle_order.index("flowers") < config.aisle_order.index("fruit")
    assert config.aisle_order.index("fruit") < config.aisle_order.index("vegetables")
    assert config.aisle_order.index("dairy/eggs") < config.aisle_order.index("meat/fish")
    assert config.aisle_order.index("meat/fish") < config.aisle_order.index("bakery")
    assert config.aisle_order.index("bakery") < config.aisle_order.index("home goods")
    assert config.aisle_order.index("home goods") < config.aisle_order.index("dry goods")
    assert config.aisle_labels["flowers"] == "Flowers"
    assert config.aisle_labels["home goods"] == "Home goods"
    assert config.aisle_labels["fruit"] == "Fruit"
    assert config.aisle_labels["meat/fish"] == "Meat & fish"
    assert "banana" in config.aisle_keywords["fruit"]
    assert "onion" in config.aisle_keywords["vegetables"]
    assert "apple cider" in config.aisle_keywords["canned drinks"]
    assert "peanut butter" in config.aisle_keywords["dry goods"]


def test_load_store_aisles_warns_when_file_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing_aisles.txt"
    load_store_aisles(str(missing))
    assert "store aisle config not found" in capsys.readouterr().err


def test_load_store_aisles_reloads_after_file_changes(tmp_path: Path) -> None:
    path = tmp_path / "store_aisles.txt"
    path.write_text(
        "# --- fruit: Fruit ---\napple\n# --- other: Other ---",
        encoding="utf-8",
    )
    first = load_store_aisles(str(path))
    assert "apple" in first.aisle_keywords["fruit"]

    path.write_text(
        "# --- fruit: Fruit ---\nbanana\n# --- other: Other ---",
        encoding="utf-8",
    )
    second = load_store_aisles(str(path))
    assert "banana" in second.aisle_keywords["fruit"]
    assert "apple" not in second.aisle_keywords["fruit"]


@pytest.mark.parametrize(
    ("item", "expected_aisle"),
    [
        ("1 lb chicken breast", "meat/fish"),
        ("1 pound loose sweet italian sausage or sausage links", "meat/fish"),
        ("2 cans artichoke hearts", "dry goods"),
        ("avocados", "fruit"),
        ("edamame", "vegetables"),
        ("lemons", "fruit"),
        ("mini cucumbers", "vegetables"),
        ("salmon / tuna", "meat/fish"),
        ("scallions", "vegetables"),
        ("seaweed sheets", "dry goods"),
        ("onions", "vegetables"),
        ("3 cloves garlic", "vegetables"),
        ("bananas", "fruit"),
        ("berries", "fruit"),
        ("2 cans white beans", "dry goods"),
        ("1 lb spaghetti", "dry goods"),
        ("eggs", "dairy/eggs"),
        ("2 eggs", "dairy/eggs"),
        ("milk", "dairy/eggs"),
        ("shredded cheddar", "refrigerated"),
        ("frozen peas", "frozen"),
        ("coffee beans", "coffee"),
        ("almonds", "nuts/dried fruit"),
        ("potato chips", "snacks"),
        ("all-purpose flour", "baking"),
        ("sourdough bread", "bakery"),
        ("8 corn tortillas", "bakery"),
        ("la croix", "canned drinks"),
        ("chicken", "meat/fish"),
        ("chimichurri", "refrigerated"),
        ("avocado oil", "dry goods"),
    ],
)
def test_classify_aisle(item: str, expected_aisle: str) -> None:
    assert classify_aisle(item) == expected_aisle


def test_sort_grocery_items_follows_store_walk_order() -> None:
    items = [
        "2 cans white beans",
        "onions",
        "bananas",
        "eggs",
        "milk",
        "1 lb chicken breast",
        "sourdough bread",
        "shredded cheddar",
        "frozen peas",
    ]
    sorted_items = sort_grocery_items(items)

    fruit_index = sorted_items.index("bananas")
    vegetables_index = sorted_items.index("onions")
    refrigerated_index = sorted_items.index("shredded cheddar")
    dairy_index = sorted_items.index("eggs")
    meat_index = sorted_items.index("1 lb chicken breast")
    bakery_index = sorted_items.index("sourdough bread")
    dry_goods_index = sorted_items.index("2 cans white beans")
    frozen_index = sorted_items.index("frozen peas")

    assert (
        fruit_index
        < vegetables_index
        < refrigerated_index
        < dairy_index
        < meat_index
        < bakery_index
        < dry_goods_index
        < frozen_index
    )
    assert sorted_items.index("milk") < meat_index


def test_group_grocery_items_by_aisle_omits_empty_aisles() -> None:
    items = ["onions", "apples", "eggs", "2 cans white beans"]
    groups = group_grocery_items_by_aisle(items)

    assert [aisle for aisle, _ in groups] == ["fruit", "vegetables", "dairy/eggs", "dry goods"]
    assert groups[0][1] == ["apples"]
    assert groups[1][1] == ["onions"]
    assert groups[2][1] == ["eggs"]
    assert groups[3][1] == ["2 cans white beans"]


def test_sort_grocery_items_is_stable_within_aisle() -> None:
    items = ["zucchini", "apples", "onions"]
    assert sort_grocery_items(items) == ["apples", "onions", "zucchini"]


def test_aisle_order_has_other_last() -> None:
    config = load_store_aisles()
    assert config.aisle_order[-1] == "other"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("- [ ] Bananas", "Bananas"),
        ("[ ] milk", "milk"),
        ("- [x] Berries", "Berries"),
        ("1. [ ] Apples", "Apples"),
        ("• onions", "onions"),
        ("  - [ ]  Asparagus  ", "Asparagus"),
    ],
)
def test_strip_checklist_prefix(raw: str, expected: str) -> None:
    assert strip_checklist_prefix(raw) == expected


@pytest.mark.parametrize(
    ("item", "expected_aisle"),
    [
        ("- [ ] Bananas", "fruit"),
        ("[ ] milk", "dairy/eggs"),
        ("- [ ] Asparagus", "vegetables"),
    ],
)
def test_classify_aisle_strips_checklist_prefix(item: str, expected_aisle: str) -> None:
    assert classify_aisle(item) == expected_aisle


@pytest.mark.parametrize(
    ("item", "expected_aisle"),
    [
        ("Apple cider", "canned drinks"),
        ("Canned peaches", "dry goods"),
        ("Raspberry jam", "dry goods"),
        ("Apricot jam", "dry goods"),
        ("Canned corn", "dry goods"),
        ("Peanut butter", "dry goods"),
        ("1 lime, juiced", "fruit"),
        ("1 pound potatoes, unpeeled but scrubbed clean", "vegetables"),
        ("Applesauce", "dry goods"),
        ("Cold foam", "dairy/eggs"),
        ("Flowers", "flowers"),
        ("- [ ] Flowers", "flowers"),
        ("Hand soap", "home goods"),
        ("Lox pastrami kind", "meat/fish"),
        ("Mexican crema", "dairy/eggs"),
        ("Pesto", "refrigerated"),
    ],
)
def test_classify_aisle_misclassifications(item: str, expected_aisle: str) -> None:
    assert classify_aisle(item) == expected_aisle
