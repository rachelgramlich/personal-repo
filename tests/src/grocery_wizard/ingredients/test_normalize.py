import pytest

from src.grocery_wizard.ingredients.normalize import (
    aggregate_amounts,
    expand_ingredient_line,
    is_junk_ingredient,
    normalize_ingredient,
    parse_amount,
    should_show_amount,
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
        ("3 packed cups coarsely chopped tuscan or curly kale", "kale"),
        ("4 teaspoons gochujang", "gochujang"),
        ("1 red onion, sliced into half-moons", "red onions"),
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
        "sliced into half-moons",
        "sliced into half moons",
        "cut into wedges",
    ],
)
def test_normalize_ingredient_junk_lines(raw: str) -> None:
    assert normalize_ingredient(raw) == ""
    assert is_junk_ingredient(raw)


def test_normalize_ingredient_keeps_chicken_with_prep_segments() -> None:
    line = "10 boneless, skinless chicken thighs (2½ to 3 pounds)"
    assert not is_junk_ingredient(line)
    assert "chicken" in normalize_ingredient(line)


def test_should_show_amount() -> None:
    assert should_show_amount("4 teaspoons", "4 teaspoons gochujang") is False
    assert should_show_amount("6 ounces", "6 ounces oyster mushrooms") is False
    assert should_show_amount("3", "3 packed cups kale") is False
    assert should_show_amount("2", "2 sweet potatoes") is True
    assert should_show_amount("1 lb", "1 lb chicken breast") is True


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


# ---------------------------------------------------------------------------
# parse_amount
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected_name", "expected_amount"),
    [
        # Recognised unit → amount includes qty + unit
        ("1 lb chicken breast", "chicken breast", "1 lb"),
        ("2 cans white beans", "white beans", "2 cans"),
        ("3 cloves garlic, minced", "garlic", "3 cloves"),
        ("8 oz tortellini", "tortellini", "8 oz"),
        ("1/2 cup all-purpose flour", "all-purpose flour", "1/2 cup"),
        ("2 tbsp olive oil, plus more for drizzling", "olive oil", "2 tbsp"),
        # Inline descriptor stripped, unit still detected
        ("2 (15-ounce) cans diced tomatoes", "diced tomatoes", "2 cans"),
        # Bare count (no recognised unit) → bare number returned
        ("2 eggs", "eggs", "2"),
        ("4 large carrots, peeled", "carrots", "4"),
        ("1 large egg, beaten", "eggs", "1"),
        ("1 medium onion, diced", "onions", "1"),
        # No leading quantity → no amount
        ("kosher salt", "kosher salt", None),
        ("fresh cilantro", "cilantro", None),
    ],
)
def test_parse_amount(raw: str, expected_name: str, expected_amount: str | None) -> None:
    name, amount = parse_amount(raw)
    assert name == expected_name
    assert amount == expected_amount


def test_parse_amount_junk_line_returns_empty_name() -> None:
    name, amount = parse_amount("rinsed and drained")
    assert name == ""
    assert amount is None


# ---------------------------------------------------------------------------
# aggregate_amounts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("amounts", "expected"),
    [
        # Same canonical unit → sum
        (["1 can", "1 can"], "2 cans"),
        (["2 cans", "1 can"], "3 cans"),
        (["1 lb", "1 lb"], "2 lb"),
        (["3 cloves", "2 cloves"], "5 cloves"),
        (["1/2 cup", "1/2 cup"], "1 cup"),
        # Mixed units → first wins
        (["1 lb", "500g"], "1 lb"),
        # Single element passes through unchanged
        (["1 can"], "1 can"),
        (["2 tbsp"], "2 tbsp"),
        # None values are skipped
        ([None, None], None),
        ([None, "2 cans"], "2 cans"),
        (["2 cans", None], "2 cans"),
        # Bare counts (no unit) → sum
        (["2", "3"], "5"),
    ],
)
def test_aggregate_amounts(amounts: list, expected: str | None) -> None:
    assert aggregate_amounts(amounts) == expected
