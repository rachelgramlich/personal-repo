"""Store aisle ordering and ingredient classification for grocery lists."""

from __future__ import annotations

from src.grocery_wizard.ingredients.normalize import parse_amount

AISLE_ORDER: tuple[str, ...] = (
    "produce",
    "refrigerated",
    "canned drinks",
    "dairy/eggs",
    "bakery",
    "dry goods",
    "baking",
    "frozen",
    "crackers/cookies",
    "coffee",
    "nuts/dried fruit",
    "snacks",
    "other",
)

AISLE_LABELS: dict[str, str] = {
    "produce": "Produce",
    "refrigerated": "Refrigerated (cheese/tofu)",
    "canned drinks": "Canned drinks",
    "dairy/eggs": "Dairy & eggs",
    "bakery": "Bakery",
    "dry goods": "Dry goods / cans / cereal / rice",
    "baking": "Baking",
    "frozen": "Frozen",
    "crackers/cookies": "Crackers & cookies",
    "coffee": "Coffee & tea",
    "nuts/dried fruit": "Nuts & dried fruit",
    "snacks": "Snacks",
    "other": "Other",
}

# Keywords checked in aisle order; longer phrases should appear first within each list.
AISLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "produce": (
        "bell pepper",
        "sweet potato",
        "green onion",
        "bok choy",
        "brussels sprouts",
        "butternut squash",
        "spaghetti squash",
        "onion",
        "onions",
        "garlic",
        "shallot",
        "ginger",
        "cilantro",
        "parsley",
        "basil",
        "mint",
        "dill",
        "thyme",
        "rosemary",
        "sage",
        "chive",
        "tomato",
        "lettuce",
        "spinach",
        "kale",
        "arugula",
        "carrot",
        "celery",
        "cucumber",
        "zucchini",
        "squash",
        "broccoli",
        "cauliflower",
        "mushroom",
        "potato",
        "jalapeño",
        "jalapeno",
        "serrano",
        "habanero",
        "lime",
        "lemon",
        "orange",
        "apple",
        "apples",
        "banana",
        "avocado",
        "berry",
        "berries",
        "strawberry",
        "blueberry",
        "raspberry",
        "corn",
        "peas",
        "bean sprouts",
        "cabbage",
        "fennel",
        "leek",
        "scallion",
        "radish",
        "beet",
        "asparagus",
        "eggplant",
        "chard",
        "grape",
        "melon",
        "mango",
        "pineapple",
        "peach",
        "pear",
        "plum",
        "herb",
        "salad greens",
        "greens",
    ),
    "refrigerated": (
        "goat cheese",
        "cream cheese",
        "parmesan",
        "mozzarella",
        "feta",
        "cheddar",
        "gruyere",
        "pecorino",
        "ricotta",
        "mascarpone",
        "provolone",
        "swiss cheese",
        "cheese",
        "tofu",
        "tempeh",
        "miso paste",
        "kimchi",
        "sauerkraut",
    ),
    "canned drinks": (
        "sparkling water",
        "ginger ale",
        "club soda",
        "la croix",
        "seltzer",
        "kombucha",
        "soda",
        "cola",
    ),
    "dairy/eggs": (
        "sour cream",
        "heavy cream",
        "whipping cream",
        "half and half",
        "greek yogurt",
        "cottage cheese",
        "cream cheese",
        "milk",
        "yogurt",
        "egg",
        "eggs",
        "butter",
    ),
    "bakery": (
        "english muffin",
        "hot dog bun",
        "hamburger bun",
        "dinner roll",
        "baguette",
        "tortilla",
        "pita",
        "naan",
        "bagel",
        "bread",
        "bun",
        "roll",
        "croissant",
    ),
    "dry goods": (
        "chicken broth",
        "beef broth",
        "vegetable broth",
        "chicken stock",
        "beef stock",
        "vegetable stock",
        "coconut milk",
        "tomato paste",
        "tomato sauce",
        "diced tomatoes",
        "crushed tomatoes",
        "canned tomatoes",
        "white beans",
        "black beans",
        "kidney beans",
        "chickpeas",
        "garbanzo",
        "lentils",
        "split peas",
        "brown rice",
        "jasmine rice",
        "basmati rice",
        "wild rice",
        "rice",
        "quinoa",
        "couscous",
        "farro",
        "barley",
        "bulgur",
        "oats",
        "oatmeal",
        "cereal",
        "granola",
        "pasta",
        "spaghetti",
        "penne",
        "rigatoni",
        "fettuccine",
        "linguine",
        "orzo",
        "noodle",
        "noodles",
        "ramen",
        "tortellini",
        "ravioli",
        "broth",
        "stock",
        "beans",
        "canned",
    ),
    "baking": (
        "chocolate chips",
        "baking powder",
        "baking soda",
        "powdered sugar",
        "brown sugar",
        "granulated sugar",
        "all-purpose flour",
        "bread flour",
        "cake flour",
        "vanilla extract",
        "cocoa powder",
        "flour",
        "sugar",
        "cornstarch",
        "yeast",
        "honey",
        "maple syrup",
        "molasses",
    ),
    "frozen": (
        "frozen peas",
        "frozen corn",
        "frozen berries",
        "ice cream",
        "frozen",
        "popsicle",
    ),
    "crackers/cookies": (
        "graham cracker",
        "ritz cracker",
        "cookie",
        "cookies",
        "cracker",
        "crackers",
        "biscuit",
        "biscuits",
    ),
    "coffee": (
        "coffee beans",
        "coffee",
        "espresso",
        "tea",
        "matcha",
    ),
    "nuts/dried fruit": (
        "dried cranberries",
        "dried apricot",
        "dried mango",
        "sun-dried tomato",
        "pine nut",
        "macadamia",
        "pistachio",
        "walnut",
        "almonds",
        "almond",
        "pecan",
        "cashew",
        "peanut",
        "hazelnut",
        "raisin",
        "raisins",
        "dates",
        "prune",
        "prunes",
        "dried fruit",
    ),
    "snacks": (
        "potato chips",
        "tortilla chips",
        "pita chips",
        "popcorn",
        "pretzel",
        "pretzels",
        "trail mix",
        "granola bar",
        "protein bar",
        "chips",
        "snack",
    ),
}


def ingredient_name(item: str) -> str:
    """Return the ingredient name from a display line, stripping any amount prefix."""
    name, _amount = parse_amount(item)
    return name or item.strip()


def classify_aisle(item: str) -> str:
    """Classify a grocery list item into a store aisle."""
    name = ingredient_name(item).lower()
    if not name:
        return "other"

    name_words = name.split()
    best_aisle = "other"
    best_keyword_len = 0
    best_aisle_rank = len(AISLE_ORDER)

    for rank, aisle in enumerate(AISLE_ORDER):
        if aisle == "other":
            continue
        for keyword in AISLE_KEYWORDS.get(aisle, ()):
            keyword_words = keyword.split()
            if _contains_word_phrase(name_words, keyword_words):
                keyword_len = len(keyword_words)
                if keyword_len > best_keyword_len or (
                    keyword_len == best_keyword_len and rank < best_aisle_rank
                ):
                    best_aisle = aisle
                    best_keyword_len = keyword_len
                    best_aisle_rank = rank

    return best_aisle


def sort_grocery_items(items: list[str]) -> list[str]:
    """Sort grocery items by store walk order, then alphabetically within each aisle."""
    aisle_rank = {aisle: index for index, aisle in enumerate(AISLE_ORDER)}

    def sort_key(item: str) -> tuple[int, str]:
        aisle = classify_aisle(item)
        return aisle_rank.get(aisle, len(AISLE_ORDER)), item.lower()

    return sorted(items, key=sort_key)


def group_grocery_items_by_aisle(items: list[str]) -> list[tuple[str, list[str]]]:
    """Group sorted grocery items by aisle, omitting empty aisles."""
    sorted_items = sort_grocery_items(items)
    groups: list[tuple[str, list[str]]] = []
    current_aisle: str | None = None
    current_items: list[str] = []

    for item in sorted_items:
        aisle = classify_aisle(item)
        if aisle != current_aisle:
            if current_items:
                groups.append((current_aisle or "other", current_items))
            current_aisle = aisle
            current_items = [item]
        else:
            current_items.append(item)

    if current_items:
        groups.append((current_aisle or "other", current_items))
    return groups


def aisle_label(aisle: str) -> str:
    return AISLE_LABELS.get(aisle, aisle.title())


def _contains_word_phrase(haystack_words: list[str], needle_words: list[str]) -> bool:
    if not needle_words or len(needle_words) > len(haystack_words):
        return False
    width = len(needle_words)
    for index in range(len(haystack_words) - width + 1):
        if haystack_words[index : index + width] == needle_words:
            return True
    return False
