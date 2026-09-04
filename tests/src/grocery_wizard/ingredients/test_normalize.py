import pytest

from src.grocery_wizard.ingredients.normalize import (
    aggregate_amounts,
    clean_ingredient_line_for_storage,
    expand_ingredient_line,
    is_instruction_line,
    is_junk_ingredient,
    is_metadata_line,
    normalize_ingredient,
    parse_amount,
    should_show_amount,
    split_compound_ingredients,
    split_merged_ingredient_line,
    split_recipe_title_bleed,
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
    ("raw", "expected"),
    [
        ("2 small yellow onions, sliced 1/4 inch thick lengthwise", "2 small yellow onions"),
        ("1 onion, diced", "1 onion"),
        ("3 cloves garlic, minced", "3 cloves garlic"),
        (
            "1 chicken bouillon cube (or substitute 2 cups chicken broth for the water bouillon)",
            "1 chicken bouillon cube (or substitute 2 cups chicken broth for the water bouillon)",
        ),
    ],
)
def test_clean_ingredient_line_for_storage(raw: str, expected: str) -> None:
    assert clean_ingredient_line_for_storage(raw) == expected


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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Optional: 1 lb ground chicken, turkey, or beef", "ground chicken"),
        ("3 garlic cloves, minced or grated", "garlic"),
        ("Crushed red pepper", "crushed red pepper"),
        ("1 cup/110 grams almond flour (ground almonds)", "almond flour"),
        ("2 (15-ounce) cans diced tomatoes", "diced tomatoes"),
        ("1 lb ground turkey", "ground turkey"),
        ("10 oz frozen spinach", "frozen spinach"),
    ],
)
def test_normalize_ingredient_notion_edge_cases(raw: str, expected: str) -> None:
    assert normalize_ingredient(raw) == expected


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


def test_is_metadata_line() -> None:
    assert is_metadata_line("Recipe serves 2")
    assert is_metadata_line("Serves 4")
    assert not is_metadata_line("1 small onion")


def test_is_instruction_line() -> None:
    assert is_instruction_line("1.\tHeat the olive oil")
    assert is_instruction_line("stir to combine.")
    assert not is_instruction_line("2 tablespoons olive oil")


def test_split_merged_ingredient_line() -> None:
    text = "2 pounds Idaho Burbank Russets2 Tablespoons scallions, finely mincedSalt"
    assert split_merged_ingredient_line(text) == [
        "2 pounds Idaho Burbank Russets",
        "2 Tablespoons scallions, finely minced",
        "Salt",
    ]
    assert split_merged_ingredient_line("Salt fresh black pepper") == [
        "Salt",
        "fresh black pepper",
    ]


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
        # Bare counts (no unit) → sum and round up for shopping
        (["2", "3"], "5"),
        (["1", "1/2"], "2"),
        (["1/2", "1/2"], "1"),
    ],
)
def test_aggregate_amounts(amounts: list, expected: str | None) -> None:
    assert aggregate_amounts(amounts) == expected


def test_split_recipe_title_bleed() -> None:
    assert split_recipe_title_bleed("chimichurri zucchini orzo") == [
        "chimichurri",
        "zucchini",
        "orzo",
    ]
    assert split_recipe_title_bleed("gnocchi sauce veggie for gnocchi") == [
        "gnocchi",
        "veggie for gnocchi",
    ]
    assert split_recipe_title_bleed("cilantro and lime wedges") == ["cilantro and lime wedges"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1 (1-inch) piece fresh ginger, peeled and grated", "ginger"),
        ("cilantro leaves", "cilantro"),
        ("asparagus trimmed thinly sliced on an angle", "asparagus"),
        (
            "1 pound boneless, skinless chicken thighs, cut into 1-inch pieces",
            "chicken thighs",
        ),
        ("¼ cup loosely packed basil leaves, rolled and julienned", "basil"),
        ("2 garlic cloves, smashed and peeled", "garlic"),
        ("1, 15oz can cannellini beans, drained and rinsed", "cannellini beans"),
    ],
)
def test_normalize_ingredient_display_name_fixes(raw: str, expected: str) -> None:
    assert normalize_ingredient(raw) == expected


def test_parse_amount_fractional_lime() -> None:
    name, amount = parse_amount("1/2 lime")
    assert name == "limes"
    assert amount == "1/2"


def test_aggregate_amounts_rounds_up_limes() -> None:
    assert aggregate_amounts(["1", "1/2"]) == "2"


@pytest.mark.parametrize(
    ("raw", "expected_name", "expected_amount"),
    [
        ("juice of half a lemon", "lemons", "1/2"),
        ("zest of 1 lemon", "lemons", "1"),
        ("Juice of 1/2 lemon, to taste", "lemons", "1/2"),
        ("1 lemon", "lemons", "1"),
        ("2 lemons", "lemons", "2"),
    ],
)
def test_parse_amount_lemon_variants(raw: str, expected_name: str, expected_amount: str) -> None:
    name, amount = parse_amount(raw)
    assert name == expected_name
    assert amount == expected_amount


def test_aggregate_amounts_consolidates_lemon_variants() -> None:
    amounts = [
        parse_amount("juice of half a lemon")[1],
        parse_amount("1 lemon")[1],
        parse_amount("zest of 1 lemon")[1],
    ]
    assert aggregate_amounts(amounts) == "3"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("or canned chickpeas", "canned chickpeas"),
        ("sherry vinegar more", "sherry vinegar"),
        ("extra-virgin olive oil more", "extra-virgin olive oil"),
        ("to 2 cups loosely packed celery leaves", "celery"),
        ("4 or 6 small celery stalks", "celery stalks"),
        ("juice of half a lemons", "lemons"),
        ("zest of 1 lemons", "lemons"),
        ("3 tablespoons sherry vinegar, more as needed", "sherry vinegar"),
        ("4 cups cooked or canned chickpeas", "canned chickpeas"),
        (
            "4 large or 6 small celery stalks, trimmed (reserve the leaves)",
            "celery stalks",
        ),
        ("1 to 2 cups loosely packed celery leaves", "celery"),
    ],
)
def test_normalize_ingredient_grocery_list_fixes(raw: str, expected: str) -> None:
    assert normalize_ingredient(raw) == expected


def test_parse_amount_quantity_range_uses_higher_bound() -> None:
    name, amount = parse_amount("4 or 6 small celery stalks")
    assert name == "celery stalks"
    assert amount == "6"


def test_notion_fixture_normalize(notion_case: dict) -> None:
    """Notion-derived lines: normalize_ingredient matches fixture expectations."""
    raw = notion_case["raw_line"]
    expected = notion_case["expect_normalized"]
    result = normalize_ingredient(raw)

    if expected is None:
        assert result == ""
    else:
        assert result == expected
