from bs4 import BeautifulSoup

from projects.grocery_wizard.scraper import (
    ScrapeError,
    _extract_ingredients,
    _extract_instagram_caption,
    _extract_json_ld_ingredients,
    _looks_like_ingredient_line,
    _scrape_instagram,
    _scrape_tiktok,
    scrape_recipe,
)

ATK_STYLE_HTML = """
<html>
  <head>
    <title>Grilled Balsamic Chicken with Peaches and Basil</title>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Recipe",
      "name": "Grilled Balsamic Chicken with Peaches and Basil",
      "recipeIngredient": [
        "¾ cup balsamic vinegar, divided",
        "3 tablespoons honey, divided",
        "1 tablespoon Dijon mustard",
        "2 garlic cloves, minced to paste",
        "1 teaspoon chopped fresh thyme leaves",
        "1½ teaspoons kosher salt, divided",
        "½ teaspoon pepper",
        "5 tablespoons extra-virgin olive oil, divided, plus more for serving",
        "10 boneless, skinless chicken thighs (2½ to 3 pounds)",
        "¼ teaspoon red pepper flakes",
        "1 pound ripe peaches, halved",
        "½ small red onion, halved",
        "½ cup basil leaves, torn"
      ]
    }
    </script>
  </head>
  <body>
    <h1>Grilled Balsamic Chicken with Peaches and Basil</h1>
    <div class="Ingredients_container__a5RnI">
      <h2>Ingredients</h2>
      <fieldset>
        <legend>Ingredient check list</legend>
        <div class="Ingredients_ingredient__j6REm">¾ cup balsamic vinegar , divided</div>
        <div class="Ingredients_ingredient__j6REm">3 tablespoons honey , divided</div>
        <div class="Ingredients_ingredient__j6REm">1 tablespoon Dijon mustard</div>
        <div class="Ingredients_ingredient__j6REm">2 garlic cloves, minced to paste</div>
        <div class="Ingredients_ingredient__j6REm">1 teaspoon chopped fresh thyme leaves</div>
        <div class="Ingredients_ingredient__j6REm">1½ teaspoons kosher salt , divided</div>
        <div class="Ingredients_ingredient__j6REm">½ teaspoon pepper</div>
        <div class="Ingredients_ingredient__j6REm">5 tablespoons extra-virgin olive oil , divided</div>
        <div class="Ingredients_ingredient__j6REm">10 boneless, skinless chicken thighs (2½ to 3 pounds)</div>
        <div class="Ingredients_ingredient__j6REm">¼ teaspoon red pepper flakes</div>
        <div class="Ingredients_ingredient__j6REm">1 pound ripe peaches, halved</div>
        <div class="Ingredients_ingredient__j6REm">½ small red onion, halved</div>
        <div class="Ingredients_ingredient__j6REm">½ cup basil leaves, torn</div>
      </fieldset>
    </div>
    <div class="instructions_container__abc">
      <h2>Instructions</h2>
      <ol class="instructions_instructionsList__1j00t">
        <li>Combine ¼ cup balsamic vinegar and remaining ingredients in a large bowl.</li>
        <li>Meanwhile, simmer remaining balsamic vinegar until reduced by half.</li>
        <li>Grill chicken for 6 to 8 minutes on each side until browned.</li>
      </ol>
    </div>
  </body>
</html>
"""

HEADING_LIST_HTML = """
<html>
  <body>
    <h1>Simple Pasta</h1>
    <h2>Ingredients</h2>
    <ul>
      <li>8 oz spaghetti</li>
      <li>2 tablespoons olive oil</li>
      <li>2 cloves garlic, minced</li>
    </ul>
  </body>
</html>
"""

JSON_LD_ONLY_HTML = """
<html>
  <body>
    <h1>JSON-LD Recipe</h1>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "WebPage",
          "name": "Wrapper"
        },
        {
          "@type": "Recipe",
          "recipeIngredient": [
            "1 cup flour",
            "2 eggs"
          ]
        }
      ]
    }
    </script>
  </body>
</html>
"""


FRAGMENTED_WPRM_HTML = """
<html>
  <body>
    <h1>Sticky Sesame Chickpeas</h1>
    <h2>Ingredients</h2>
    <div class="wprm-recipe-ingredients-container">
      <ul>
        <li class="wprm-recipe-ingredient">
          <span class="wprm-recipe-ingredient-amount">2</span>
          <span class="wprm-recipe-ingredient-unit">15 ounce cans</span>
          <span class="wprm-recipe-ingredient-name">chickpeas</span>
        </li>
        <li class="wprm-recipe-ingredient">
          <span class="wprm-recipe-ingredient-amount">3</span>
          <span class="wprm-recipe-ingredient-unit">tablespoons</span>
          <span class="wprm-recipe-ingredient-name">maple syrup</span>
        </li>
        <li class="wprm-recipe-ingredient">
          <span class="wprm-recipe-ingredient-amount">2</span>
          <span class="wprm-recipe-ingredient-unit">teaspoons</span>
          <span class="wprm-recipe-ingredient-name">rice vinegar</span>
        </li>
      </ul>
    </div>
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "recipeIngredient": [
        "2 15 ounce cans chickpeas",
        "3 tablespoons maple syrup",
        "2 teaspoons rice vinegar"
      ]
    }
    </script>
  </body>
</html>
"""

FRAGMENTED_TOKEN_LIST_HTML = """
<html>
  <body>
    <h2>Ingredients</h2>
    <ul>
      <li>2</li>
      <li>tablespoons</li>
      <li>cocoa powder</li>
      <li>1</li>
      <li>1/2</li>
      <li>cups</li>
      <li>sugar</li>
      <li>3</li>
      <li>tablespoons</li>
      <li>corn starch</li>
    </ul>
  </body>
</html>
"""

CHESS_PIE_WPRM_HTML = """
<html>
  <body>
    <h3>Ingredients</h3>
    <ul>
      <li class="wprm-recipe-ingredient">
        <span class="wprm-recipe-ingredient-amount">4</span>
        <span class="wprm-recipe-ingredient-unit">tablespoons</span>
        <span class="wprm-recipe-ingredient-name">cocoa powder</span>
      </li>
      <li class="wprm-recipe-ingredient">
        <span class="wprm-recipe-ingredient-amount">4</span>
        <span class="wprm-recipe-ingredient-unit">tablespoons</span>
        <span class="wprm-recipe-ingredient-name">unsalted butter</span>
        <span class="wprm-recipe-ingredient-notes">(melted)</span>
      </li>
      <li class="wprm-recipe-ingredient">
        <span class="wprm-recipe-ingredient-amount">1</span>
        <span class="wprm-recipe-ingredient-unit">(9-inch)</span>
        <span class="wprm-recipe-ingredient-name">unbaked pie crust</span>
      </li>
    </ul>
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "recipeIngredient": [
        "4 tablespoons cocoa powder",
        "4 tablespoons unsalted butter (melted)",
        "1 (9-inch) unbaked pie crust"
      ]
    }
    </script>
  </body>
</html>
"""


def test_extract_ingredients_wprm_span_tokens_use_json_ld() -> None:
    soup = BeautifulSoup(FRAGMENTED_WPRM_HTML, "html.parser")
    ingredients = _extract_ingredients(soup)

    assert ingredients == [
        "2 15 ounce cans chickpeas",
        "3 tablespoons maple syrup",
        "2 teaspoons rice vinegar",
    ]


def test_extract_ingredients_joins_fragmented_token_list() -> None:
    soup = BeautifulSoup(FRAGMENTED_TOKEN_LIST_HTML, "html.parser")
    ingredients = _extract_ingredients(soup)

    assert ingredients == [
        "2 tablespoons cocoa powder",
        "1 1/2 cups sugar",
        "3 tablespoons corn starch",
    ]


def test_extract_ingredients_chess_pie_wprm_markup() -> None:
    soup = BeautifulSoup(CHESS_PIE_WPRM_HTML, "html.parser")
    ingredients = _extract_ingredients(soup)

    assert ingredients == [
        "4 tablespoons cocoa powder",
        "4 tablespoons unsalted butter (melted)",
        "1 (9-inch) unbaked pie crust",
    ]

    soup = BeautifulSoup(ATK_STYLE_HTML, "html.parser")
    ingredients = _extract_ingredients(soup)

    assert len(ingredients) == 13
    assert ingredients[0] == "¾ cup balsamic vinegar , divided"
    assert ingredients[1] == "3 tablespoons honey , divided"
    assert "chicken thighs" in ingredients[8]
    assert not any(item.startswith("Combine") for item in ingredients)
    assert not any(item.startswith("Meanwhile") for item in ingredients)


def test_extract_ingredients_heading_ul_still_works() -> None:
    soup = BeautifulSoup(HEADING_LIST_HTML, "html.parser")
    ingredients = _extract_ingredients(soup)

    assert ingredients == [
        "8 oz spaghetti",
        "2 tablespoons olive oil",
        "2 cloves garlic, minced",
    ]


def test_extract_json_ld_from_graph() -> None:
    soup = BeautifulSoup(JSON_LD_ONLY_HTML, "html.parser")
    ingredients = _extract_json_ld_ingredients(soup)

    assert ingredients == ["1 cup flour", "2 eggs"]


def test_atk_fixture_falls_back_to_json_ld_when_heading_points_to_instructions(
    monkeypatch,
) -> None:
    broken_html = """
    <html>
      <body>
        <h2>Ingredients</h2>
        <ol class="instructions_instructionsList__1j00t">
          <li>Combine vinegar and honey in a bowl and whisk until smooth.</li>
          <li>Meanwhile, simmer balsamic vinegar until reduced by half.</li>
        </ol>
        <script type="application/ld+json">
        {
          "@type": "Recipe",
          "recipeIngredient": ["1 cup balsamic vinegar", "1 tablespoon honey"]
        }
        </script>
      </body>
    </html>
    """

    def fake_get(url, headers=None, timeout=None):
        class FakeResponse:
            content = broken_html.encode()
            status_code = 200

            def raise_for_status(self):
                return None

        return FakeResponse()

    monkeypatch.setattr("projects.grocery_wizard.scraper.requests.get", fake_get)

    scraped = scrape_recipe("https://example.com/atk-recipe")
    assert scraped.ingredients == ["1 cup balsamic vinegar", "1 tablespoon honey"]


TIKTOK_HTML = """
<html>
  <body>
    <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">
    {
      "__DEFAULT_SCOPE__": {
        "webapp.video-detail": {
          "itemInfo": {
            "itemStruct": {
              "desc": "Tomato pasta salad with a bright vinaigrette",
              "contents": [
                {"desc": "Tomato pasta salad"},
                {"desc": "Tomato vin -"},
                {"desc": "1/2 cup evoo"},
                {"desc": "1/4 cup champagne vinegar"},
                {"desc": "1 large garlic clove, grated"},
                {"desc": "1 pinch salt"}
              ]
            }
          }
        }
      }
    }
    </script>
  </body>
</html>
"""


def test_tiktok_ingredient_line_detection() -> None:
    assert _looks_like_ingredient_line("1/2 cup evoo")
    assert not _looks_like_ingredient_line("Tomato pasta salad")
    assert not _looks_like_ingredient_line("Combine vinegar and oil in a bowl.")


def test_scrape_tiktok_extracts_caption_ingredients(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None, allow_redirects=None):
        class FakeResponse:
            content = TIKTOK_HTML.encode()
            status_code = 200

            def raise_for_status(self):
                return None

        return FakeResponse()

    monkeypatch.setattr("projects.grocery_wizard.scraper.requests.get", fake_get)

    scraped = _scrape_tiktok("https://www.tiktok.com/t/example/")
    assert scraped.title == "Tomato Pasta Salad"
    assert scraped.ingredients == [
        "1/2 cup evoo",
        "1/4 cup champagne vinegar",
        "1 large garlic clove, grated",
        "1 pinch salt",
    ]


def test_scrape_tiktok_raises_when_no_ingredients(monkeypatch) -> None:
    empty_html = """
    <html><body>
      <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">
      {"__DEFAULT_SCOPE__":{"webapp.video-detail":{"itemInfo":{"itemStruct":{"desc":"Just vibes","contents":[{"desc":"No ingredients here"}]}}}}}
      </script>
    </body></html>
    """

    def fake_get(url, headers=None, timeout=None, allow_redirects=None):
        class FakeResponse:
            content = empty_html.encode()
            status_code = 200

            def raise_for_status(self):
                return None

        return FakeResponse()

    monkeypatch.setattr("projects.grocery_wizard.scraper.requests.get", fake_get)

    try:
        _scrape_tiktok("https://www.tiktok.com/t/example/")
        raised = False
    except ScrapeError:
        raised = True
    assert raised


INSTAGRAM_OG_HTML = """
<html>
  <head>
    <meta property="og:title" content="chefname on Instagram: &quot;Sheet Pan Lemon Chicken&quot;" />
    <meta property="og:description" content="Sheet Pan Lemon Chicken\n\nIngredients:\n1 lb chicken thighs\n2 tbsp olive oil\n1 lemon, sliced\n2 cloves garlic, minced\n1 tsp dried oregano\nsalt and pepper" />
  </head>
  <body></body>
</html>
"""

INSTAGRAM_JSON_LD_HTML = """
<html>
  <head>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "VideoObject",
      "name": "Creamy Tuscan Pasta",
      "description": "Creamy Tuscan Pasta\\n\\n1/2 lb pasta\\n1 cup heavy cream\\n2 cups spinach\\n1/4 cup sun-dried tomatoes"
    }
    </script>
  </head>
  <body></body>
</html>
"""

INSTAGRAM_SCRIPT_JSON_HTML = """
<html>
  <body>
    <script type="application/json">
    {
      "graphql": {
        "shortcode_media": {
          "edge_media_to_caption": {
            "edges": [
              {"node": {"text": "Garlic Butter Shrimp\\n\\n1 lb shrimp\\n4 tbsp butter\\n4 cloves garlic\\n1/4 tsp red pepper flakes"}}
            ]
          }
        }
      }
    }
    </script>
  </body>
</html>
"""


def test_extract_instagram_caption_from_og_description() -> None:
    soup = BeautifulSoup(INSTAGRAM_OG_HTML, "html.parser")
    caption = _extract_instagram_caption(soup, INSTAGRAM_OG_HTML)

    assert "Sheet Pan Lemon Chicken" in caption
    assert "1 lb chicken thighs" in caption


def test_scrape_instagram_extracts_caption_ingredients(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None, allow_redirects=None):
        class FakeResponse:
            content = INSTAGRAM_OG_HTML.encode()
            status_code = 200

            def raise_for_status(self):
                return None

        return FakeResponse()

    monkeypatch.setattr("projects.grocery_wizard.scraper.requests.get", fake_get)

    scraped = _scrape_instagram("https://www.instagram.com/reel/DZz61Yhx2DC/")
    assert scraped.title == "Sheet Pan Lemon Chicken"
    assert scraped.ingredients == [
        "1 lb chicken thighs",
        "2 tbsp olive oil",
        "1 lemon, sliced",
        "2 cloves garlic, minced",
        "1 tsp dried oregano",
    ]


def test_scrape_instagram_from_json_ld(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None, allow_redirects=None):
        class FakeResponse:
            content = INSTAGRAM_JSON_LD_HTML.encode()
            status_code = 200

            def raise_for_status(self):
                return None

        return FakeResponse()

    monkeypatch.setattr("projects.grocery_wizard.scraper.requests.get", fake_get)

    scraped = scrape_recipe("https://www.instagram.com/reel/example/")
    assert scraped.title == "Creamy Tuscan Pasta"
    assert scraped.ingredients == [
        "1/2 lb pasta",
        "1 cup heavy cream",
        "2 cups spinach",
        "1/4 cup sun-dried tomatoes",
    ]


def test_scrape_instagram_from_script_json(monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None, allow_redirects=None):
        class FakeResponse:
            content = INSTAGRAM_SCRIPT_JSON_HTML.encode()
            status_code = 200

            def raise_for_status(self):
                return None

        return FakeResponse()

    monkeypatch.setattr("projects.grocery_wizard.scraper.requests.get", fake_get)

    scraped = scrape_recipe("https://www.instagram.com/p/example/")
    assert scraped.title == "Garlic Butter Shrimp"
    assert scraped.ingredients == [
        "1 lb shrimp",
        "4 tbsp butter",
        "4 cloves garlic",
        "1/4 tsp red pepper flakes",
    ]


def test_scrape_instagram_raises_when_no_ingredients(monkeypatch) -> None:
    empty_html = """
    <html><head>
      <meta property="og:description" content="Just a fun reel with no recipe list" />
    </head><body></body></html>
    """

    def fake_get(url, headers=None, timeout=None, allow_redirects=None):
        class FakeResponse:
            content = empty_html.encode()
            status_code = 200

            def raise_for_status(self):
                return None

        return FakeResponse()

    monkeypatch.setattr("projects.grocery_wizard.scraper.requests.get", fake_get)

    try:
        _scrape_instagram("https://www.instagram.com/reel/example/")
        raised = False
    except ScrapeError as exc:
        raised = True
        assert "No ingredient lines found" in str(exc)
        assert "Paste ingredients manually" in str(exc)
    assert raised
