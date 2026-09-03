import pytest

from projects.grocery_wizard.ingredient_normalize import (
    expand_ingredient_line,
    is_junk_ingredient,
    normalize_ingredient,
    split_compound_ingredients,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1 large egg, beaten", "eggs"),
        ("2 tablespoons olive oil, plus more for drizzling", "olive oil"),
        ("kosher salt", "kosher salt"),
        ("1/2 cup all-purpose flour", "all-purpose flour"),
        ("3 cloves garlic, minced", "garlic"),
        ("1 medium onion, diced", "onions"),
        ("Salt and pepper to taste", "salt and pepper"),
        ("2 (15-ounce) cans diced tomatoes", "diced tomatoes"),
        ("Freshly ground black pepper", "black pepper"),
        ("Chopped fresh cilantro", "cilantro"),
        ("1 can chickpeas, rinsed and drained", "chickpeas"),
        ("lime wedges", "limes"),
        ("1 lime, cut into wedges (optional)", "limes"),
    ],
)
def test_normalize_ingredient(raw: str, expected: str) -> None:
    assert normalize_ingredient(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "rinsed",
        "drained",
        "rinsed and drained",
        "Rinsed and drained",
        "for garnish",
        "to serve",
        "optional",
    ],
)
def test_normalize_ingredient_junk_lines(raw: str) -> None:
    assert normalize_ingredient(raw) == ""
    assert is_junk_ingredient(raw)


def test_normalize_ingredient_empty() -> None:
    assert normalize_ingredient("") == ""
    assert normalize_ingredient("   ") == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "Naan bread and rice, to serve (optional)",
            ["Naan bread", "rice, to serve (optional)"],
        ),
        (
            "Chopped fresh cilantro and lime wedges, for garnish (optional)",
            ["Chopped fresh cilantro", "lime wedges, for garnish (optional)"],
        ),
        ("Salt and pepper to taste", ["Salt and pepper to taste"]),
        ("1 onion, diced, and 2 cloves garlic", ["1 onion, diced", "2 cloves garlic"]),
        ("cauliflower rice", ["cauliflower rice"]),
        ("cauliflower and rice", ["cauliflower", "rice"]),
        ("cauliflower & rice", ["cauliflower", "rice"]),
        ("brown rice", ["brown rice"]),
    ],
)
def test_expand_ingredient_line(raw: str, expected: list[str]) -> None:
    assert expand_ingredient_line(raw) == expected


def test_expand_ingredient_line_does_not_split_color_variants() -> None:
    assert expand_ingredient_line("red and green bell peppers") == ["red and green bell peppers"]


def test_expand_ingredient_line_does_not_split_white_beans() -> None:
    assert expand_ingredient_line("2 cans white beans") == ["2 cans white beans"]
    assert expand_ingredient_line("–2 cans white beans") == ["-2 cans white beans"]


def test_normalize_ingredient_white_beans() -> None:
    assert normalize_ingredient("2 cans white beans") == "white beans"
    assert normalize_ingredient("– 2 cans white beans") == "white beans"
    assert normalize_ingredient("–2 cans white beans") == "white beans"


def test_split_compound_ingredients_multiline() -> None:
    text = (
        "Naan bread and rice, to serve (optional)\n"
        "Salt and pepper to taste\n"
        "1 onion, diced, and 2 cloves garlic"
    )
    assert split_compound_ingredients(text) == [
        "Naan bread",
        "rice, to serve (optional)",
        "Salt and pepper to taste",
        "1 onion, diced",
        "2 cloves garlic",
    ]


def test_split_compound_ingredients_empty() -> None:
    assert split_compound_ingredients("") == []
    assert split_compound_ingredients("   \n") == []
