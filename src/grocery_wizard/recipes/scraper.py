"""Scrape recipe title and ingredients from a URL."""

from __future__ import annotations

__all__ = [
    "INSTAGRAM_MANUAL_HINT",
    "TIKTOK_MANUAL_HINT",
    "ScrapeError",
    "ScrapedRecipe",
    "has_merge_artifacts",
    "ingredients_to_text",
    "looks_fragmented",
    "scrape_recipe",
]

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag

from src.grocery_wizard.ingredients.normalize import drop_junk_ingredient_lines

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30
TIKTOK_MANUAL_HINT = (
    "TikTok recipes often list ingredients in the video caption only. "
    "Paste ingredients manually into the Notion Ingredients column, "
    "or use a recipe blog link instead."
)
INSTAGRAM_MANUAL_HINT = (
    "Instagram recipes often list ingredients in the reel caption only. "
    "Paste ingredients manually into the Notion Ingredients column, "
    "or use a recipe blog link instead."
)

_INGREDIENTS_HEADING = re.compile(r"^ingredients$", re.IGNORECASE)
_INSTRUCTION_CLASS = re.compile(r"instruction", re.IGNORECASE)
_INGREDIENT_ITEM_CLASS = re.compile(
    r"(?<![s])ingredient(?:[_-]\w+|$)",
    re.IGNORECASE,
)
_INSTRUCTION_START = re.compile(
    r"^(combine|meanwhile|when ready|for a |clean and|grill|cut |spoon|serve|"
    r"transfer|brush|arrange|heat |reduce |bring |pat |whisk |cover|open )",
    re.IGNORECASE,
)
_INGREDIENT_LINE = re.compile(
    r"(?:\b\d+\b|\b\d+/\d+\b|\bcup\b|\btbsp\b|\btsp\b|\boz\b|\blb\b|\bclove\b|\bpinch\b)",
    re.IGNORECASE,
)
_QUANTITY_START = re.compile(
    r"^(?:\d+(?:[./]\d+)?|\d+\s+\d+/\d+|\d+-\d+|\d+\s*-\s*\d+)",
)
_UNIT_ONLY = re.compile(
    r"^(?:cups?|tablespoons?|tbsp|teaspoons?|tsp|ounces?|oz|pounds?|lbs?|grams?|g|"
    r"kilograms?|kg|milliliters?|ml|liters?|l|cloves?|pinch(?:es)?|dash(?:es)?|"
    r"can(?:s)?|package(?:s)?|bunch(?:es)?|stalk(?:s)?|sprigs?|slices?|pieces?|"
    r"heads?|stalks?|sticks?|large|medium|small|whole|heaping|scant)\.?$",
    re.IGNORECASE,
)
_FOOD_WORD = re.compile(
    r"\b(?:chicken|beef|pork|fish|salmon|shrimp|tofu|egg|milk|cream|butter|oil|"
    r"flour|sugar|salt|pepper|garlic|onion|tomato|cheese|rice|pasta|bean|chickpea|"
    r"lentil|spinach|lemon|lime|honey|vinegar|mustard|herb|basil|thyme|oregano|"
    r"cumin|paprika|cinnamon|ginger|carrot|potato|broccoli|mushroom|corn|peach|"
    r"chocolate|cocoa|vanilla|nut|almond|walnut|pecan|sesame|soy|sauce|stock|broth|"
    r"water|wine|bread|noodle|sausage|bacon|ham|turkey|lamb|shrimp|scallop|crab|"
    r"avocado|cilantro|parsley|mint|dill|chili|pepper|jalapeño|zucchini|squash|"
    r"kale|lettuce|cabbage|celery|ginger|turmeric|coriander|cardamom|nutmeg|clove|"
    r"yeast|baking|powder|soda|cornstarch|molasses|syrup|maple|brown|rice|quinoa|"
    r"oat|barley|couscous|tortilla|wrap|pita|mayo|mayonnaise|yogurt|sour|cream|"
    r"coconut|miso|tahini|peanut|almond|cashew|anchovy|cap|er|olive|vegetable|canola|"
    r"sesame|chickpea|powder|crumb|breadcrumb|cracker|pie|crust|filling)\b",
    re.IGNORECASE,
)


class ScrapeError(Exception):
    """Recipe could not be scraped from the URL."""


@dataclass(frozen=True, slots=True)
class ScrapedRecipe:
    url: str
    title: str
    ingredients: list[str]
    total_time_minutes: float | None = None


def scrape_recipe(url: str) -> ScrapedRecipe:
    if _is_tiktok_url(url):
        return _scrape_tiktok(url)
    if _is_instagram_url(url):
        return _scrape_instagram(url)

    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    title = _extract_title(soup)
    ingredients = _extract_ingredients(soup)
    total_time_minutes = _extract_json_ld_cook_time_minutes(soup)

    return ScrapedRecipe(
        url=url,
        title=title,
        ingredients=ingredients,
        total_time_minutes=total_time_minutes,
    )


def _is_tiktok_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "tiktok.com" in host


def _is_instagram_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "instagram.com" in host


def _scrape_instagram(url: str) -> ScrapedRecipe:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()

    html = response.content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(response.content, "html.parser")
    caption = _extract_instagram_caption(soup, html)
    if not caption:
        raise ScrapeError(f"Could not read Instagram reel caption. {INSTAGRAM_MANUAL_HINT}")

    title = _instagram_title(caption, soup)
    ingredients = _caption_ingredients(caption)
    if not ingredients:
        raise ScrapeError(
            f"No ingredient lines found in Instagram caption. {INSTAGRAM_MANUAL_HINT}"
        )

    return ScrapedRecipe(url=url, title=title, ingredients=ingredients)


def _extract_instagram_caption(soup: BeautifulSoup, html: str) -> str:
    for extractor in (
        lambda: _instagram_caption_from_meta(soup),
        lambda: _instagram_caption_from_json_ld(soup),
        lambda: _instagram_caption_from_shared_data(html),
        lambda: _instagram_caption_from_script_json(html),
    ):
        caption = extractor()
        if caption:
            return caption
    return ""


def _instagram_caption_from_meta(soup: BeautifulSoup) -> str:
    for prop in ("og:description", "description", "twitter:description"):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if isinstance(tag, Tag) and tag.get("content"):
            return _decode_instagram_text(str(tag["content"]))
    return ""


def _instagram_caption_from_json_ld(soup: BeautifulSoup) -> str:
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string or script.get_text()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        caption = _instagram_caption_from_json_ld_data(data)
        if caption:
            return caption
    return ""


def _instagram_caption_from_json_ld_data(data: object) -> str:
    if isinstance(data, list):
        for item in data:
            caption = _instagram_caption_from_json_ld_data(item)
            if caption:
                return caption
        return ""

    if not isinstance(data, dict):
        return ""

    for key in ("description", "caption", "articleBody"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return _decode_instagram_text(value)

    for key in ("@graph", "mainEntity"):
        nested = data.get(key)
        if nested is not None:
            caption = _instagram_caption_from_json_ld_data(nested)
            if caption:
                return caption

    return ""


def _instagram_caption_from_shared_data(html: str) -> str:
    match = re.search(r"window\._sharedData\s*=\s*(\{.*?\});</script>", html, re.DOTALL)
    if not match:
        return ""

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return ""

    return _instagram_caption_from_graphql_payload(data)


def _instagram_caption_from_script_json(html: str) -> str:
    for script_text in re.findall(
        r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL,
    ):
        if '"caption"' not in script_text and '"edge_media_to_caption"' not in script_text:
            continue
        try:
            data = json.loads(script_text)
        except json.JSONDecodeError:
            continue
        caption = _instagram_caption_from_graphql_payload(data)
        if caption:
            return caption

    for match in re.finditer(
        r'"caption"\s*:\s*\{\s*"text"\s*:\s*"((?:\\.|[^"\\])*)"',
        html,
    ):
        caption = _decode_instagram_text(match.group(1))
        if caption:
            return caption

    for match in re.finditer(
        r'"edge_media_to_caption"\s*:\s*\{\s*"edges"\s*:\s*\[\s*\{\s*"node"\s*:\s*\{\s*"text"\s*:\s*"((?:\\.|[^"\\])*)"',
        html,
    ):
        caption = _decode_instagram_text(match.group(1))
        if caption:
            return caption

    return ""


def _instagram_caption_from_graphql_payload(data: object) -> str:
    if isinstance(data, dict):
        for key in ("caption", "text"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return _decode_instagram_text(value)
            if isinstance(value, dict):
                nested = value.get("text")
                if isinstance(nested, str) and nested.strip():
                    return _decode_instagram_text(nested)

        edges = data.get("edges")
        if isinstance(edges, list):
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                node = edge.get("node")
                if isinstance(node, dict):
                    text = node.get("text")
                    if isinstance(text, str) and text.strip():
                        return _decode_instagram_text(text)

        for value in data.values():
            caption = _instagram_caption_from_graphql_payload(value)
            if caption:
                return caption

    elif isinstance(data, list):
        for item in data:
            caption = _instagram_caption_from_graphql_payload(item)
            if caption:
                return caption

    return ""


def _decode_instagram_text(text: str) -> str:
    try:
        return json.loads(f'"{text}"')
    except json.JSONDecodeError:
        return (
            text.replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
            .strip()
        )


def _instagram_title(caption: str, soup: BeautifulSoup) -> str:
    first_line = next(
        (line.strip() for line in caption.splitlines() if line.strip()),
        "",
    )
    if first_line and not first_line.startswith("#"):
        cleaned = _clean_tiktok_caption_line(first_line)
        if cleaned:
            return cleaned

    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag) and og_title.get("content"):
        title = str(og_title["content"]).strip()
        title = re.sub(r"\s+on Instagram:.*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"^[^:]+:\s*", "", title).strip()
        if title:
            return title

    return "Instagram Recipe"


def _caption_ingredients(caption: str) -> list[str]:
    lines = [line.strip() for line in re.split(r"[\n\r]+", caption) if line.strip()]
    ingredients = [line for line in lines if _looks_like_ingredient_line(line)]
    return _dedupe_preserve_order(ingredients)


def _scrape_tiktok(url: str) -> ScrapedRecipe:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    item = _extract_tiktok_item(soup)
    if item is None:
        raise ScrapeError(f"Could not read TikTok video data. {TIKTOK_MANUAL_HINT}")

    title = _tiktok_title(item)
    ingredients = _tiktok_ingredients(item)
    if not ingredients:
        raise ScrapeError(f"No ingredient lines found in TikTok caption. {TIKTOK_MANUAL_HINT}")

    return ScrapedRecipe(url=url, title=title, ingredients=ingredients)


def _extract_tiktok_item(soup: BeautifulSoup) -> dict | None:
    script = soup.find("script", id="__UNIVERSAL_DATA_FOR_REHYDRATION__")
    if not script or not script.string:
        return None
    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return None

    item = (
        data.get("__DEFAULT_SCOPE__", {})
        .get("webapp.video-detail", {})
        .get("itemInfo", {})
        .get("itemStruct")
    )
    return item if isinstance(item, dict) else None


def _tiktok_title(item: dict) -> str:
    contents = item.get("contents") or []
    for block in contents:
        if not isinstance(block, dict):
            continue
        text = str(block.get("desc", "")).strip()
        if text and not text.startswith("#"):
            cleaned = _clean_tiktok_caption_line(text)
            if cleaned:
                return cleaned

    desc = str(item.get("desc", "")).strip()
    if desc:
        first = desc.split("\n", 1)[0].strip()
        cleaned = _clean_tiktok_caption_line(first)
        if cleaned:
            return cleaned

    return "TikTok Recipe"


def _clean_tiktok_caption_line(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"[^\w\s\-',.&]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,-")
    if len(text) > 80:
        text = text[:77].rstrip() + "..."
    return text.title() if text else ""


def _tiktok_ingredients(item: dict) -> list[str]:
    lines: list[str] = []
    for block in item.get("contents") or []:
        if not isinstance(block, dict):
            continue
        text = str(block.get("desc", "")).strip()
        if text:
            lines.append(text)

    if not lines:
        desc = str(item.get("desc", "")).strip()
        if desc:
            lines = [line.strip() for line in re.split(r"[\n\r]+", desc) if line.strip()]

    ingredients = [line for line in lines if _looks_like_ingredient_line(line)]
    return _dedupe_preserve_order(ingredients)


def _looks_like_ingredient_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if len(stripped) > 120:
        return False
    if _INSTRUCTION_START.match(stripped):
        return False
    return bool(
        _INGREDIENT_LINE.search(stripped)
        or re.match(r"^[\d/.\s]+(?:cup|tbsp|tsp|oz|lb|g|ml)\b", stripped, re.IGNORECASE)
    )


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)

    if soup.title and soup.title.string:
        return soup.title.string.strip()

    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag) and og_title.get("content"):
        return str(og_title["content"]).strip()

    return "Untitled Recipe"


def _extract_ingredients(soup: BeautifulSoup) -> list[str]:
    json_ld_ingredients = _extract_json_ld_ingredients(soup)

    heading_ingredients = _extract_heading_ingredients(soup)
    if heading_ingredients and not _looks_like_instructions(heading_ingredients):
        heading_ingredients = _normalize_ingredient_lines(heading_ingredients)
        if json_ld_ingredients and (
            looks_fragmented(heading_ingredients) or has_merge_artifacts(heading_ingredients)
        ):
            return json_ld_ingredients
        return heading_ingredients

    if json_ld_ingredients:
        return json_ld_ingredients

    return _normalize_ingredient_lines(heading_ingredients)


def _extract_heading_ingredients(soup: BeautifulSoup) -> list[str]:
    section_titles = soup.find_all(
        re.compile(r"^h\d$"),
        string=_INGREDIENTS_HEADING,
    )

    for title in section_titles:
        ingredients = _ingredients_from_heading_section(title)
        if ingredients:
            return ingredients

    return []


def _ingredients_from_heading_section(heading: Tag) -> list[str]:
    all_ingredients: list[str] = []
    for sibling in heading.find_next_siblings():
        if _is_section_heading(sibling):
            break
        all_ingredients.extend(_extract_ingredients_from_container(sibling))
    if all_ingredients:
        return all_ingredients

    parent = heading.parent
    if isinstance(parent, Tag):
        for child in parent.find_all(["fieldset", "ul", "ol", "div"], recursive=False):
            if child is heading or _is_section_heading(child):
                continue
            all_ingredients.extend(_extract_ingredients_from_container(child))
        if all_ingredients:
            return all_ingredients

    next_element = heading.find_next(["fieldset", "ul", "ol", "div"])
    while isinstance(next_element, Tag):
        if _is_section_heading(next_element) and next_element is not heading:
            break
        if not _is_instruction_container(next_element):
            all_ingredients.extend(_extract_ingredients_from_container(next_element))
        next_element = next_element.find_next(["fieldset", "ul", "ol", "div"])

    return all_ingredients


def _extract_ingredients_from_container(container: Tag) -> list[str]:
    if _is_instruction_container(container):
        return []

    list_items = [
        item
        for item in container.find_all("li", class_=_INGREDIENT_ITEM_CLASS)
        if item.get_text(strip=True)
    ]
    if not list_items and container.name in ("ul", "ol"):
        list_items = container.find_all("li", recursive=False)
    if list_items:
        texts = _clean_ingredient_texts(_texts_from_list_items(list_items))
        if texts and looks_fragmented(texts):
            joined = _join_fragmented_lines(texts)
            if joined:
                return joined
        return texts

    ingredient_items = _top_level_ingredient_items(container)
    if ingredient_items:
        texts = _clean_ingredient_texts(
            [item.get_text(" ", strip=True) for item in ingredient_items]
        )
        if texts and looks_fragmented(texts):
            joined = _join_fragmented_lines(texts)
            if joined:
                return joined
        return texts

    if container.name == "fieldset":
        texts = _clean_ingredient_texts(
            [
                item.get_text(" ", strip=True)
                for item in container.find_all(["div", "label", "li"], recursive=False)
                if item.get_text(strip=True)
                and item.name != "legend"
                and not _is_section_heading(item)
            ]
        )
        if texts and looks_fragmented(texts):
            joined = _join_fragmented_lines(texts)
            if joined:
                return joined
        return texts

    return []


def _top_level_ingredient_items(container: Tag) -> list[Tag]:
    items = container.find_all(class_=_INGREDIENT_ITEM_CLASS)
    if not items:
        return []

    item_set = set(items)
    top_level = [
        item
        for item in items
        if not any(isinstance(parent, Tag) and parent in item_set for parent in item.parents)
    ]
    li_items = [item for item in top_level if item.name == "li"]
    return li_items or top_level


def _clean_ingredient_texts(texts: list[str]) -> list[str]:
    cleaned: list[str] = []
    for text in texts:
        stripped = re.sub(r"^[▢•*]\s*", "", text.strip())
        if stripped:
            cleaned.append(stripped)
    return cleaned


def _texts_from_list_items(items: list[Tag]) -> list[str]:
    return [item.get_text(" ", strip=True) for item in items if item.get_text(strip=True)]


def _normalize_ingredient_lines(lines: list[str]) -> list[str]:
    if not lines:
        return []
    if looks_fragmented(lines):
        joined = _join_fragmented_lines(lines)
        if joined:
            return drop_junk_ingredient_lines(joined)
    return drop_junk_ingredient_lines(lines)


def looks_fragmented(lines: list[str]) -> bool:
    if len(lines) < 4:
        return False

    stripped = [line.strip() for line in lines if line.strip()]
    if len(stripped) < 4:
        return False

    fragment_count = sum(1 for line in stripped if _is_ingredient_fragment(line))
    if fragment_count / len(stripped) > 0.5:
        return True

    avg_len = sum(len(line) for line in stripped) / len(stripped)
    return len(stripped) >= 12 and avg_len < 18


def has_merge_artifacts(lines: list[str]) -> bool:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"\([^)]+\)", stripped):
            return True
        if re.search(r"\b\w+ \d+$", stripped) and not _QUANTITY_START.match(stripped):
            return True
        words = stripped.lower().split()
        for index in range(len(words) - 1):
            if words[index] == words[index + 1]:
                return True
    return False


def _is_ingredient_fragment(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True

    words = stripped.split()
    if len(words) == 1:
        if _QUANTITY_START.match(stripped):
            return True
        if _UNIT_ONLY.match(stripped):
            return True
        if re.fullmatch(r"[\d/.\-]+", stripped):
            return True
        return not _FOOD_WORD.search(stripped)

    if _UNIT_ONLY.match(stripped):
        return True
    return bool(
        _QUANTITY_START.match(stripped) and len(words) <= 2 and not _FOOD_WORD.search(stripped)
    )


def _starts_new_ingredient(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("-", "•", "*", "▢", "[")):
        return True
    return bool(_QUANTITY_START.match(stripped))


def _is_complete_ingredient(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.endswith(")") and "(" in stripped:
        return True
    if _FOOD_WORD.search(stripped) and (
        _INGREDIENT_LINE.search(stripped) or _QUANTITY_START.match(stripped)
    ):
        return True
    return len(stripped.split()) >= 3 and bool(_FOOD_WORD.search(stripped))


def _join_fragmented_lines(lines: list[str]) -> list[str]:
    stripped = [line.strip() for line in lines if line.strip()]
    if not stripped:
        return []

    joined: list[str] = []
    current = ""

    for line in stripped:
        if current and _starts_new_ingredient(line) and _is_complete_ingredient(current):
            joined.append(current)
            current = line
            continue

        if not current:
            current = line
            continue

        current = f"{current} {line}".strip()

        if _is_complete_ingredient(current):
            joined.append(current)
            current = ""

    if current:
        if joined and _is_ingredient_fragment(current):
            joined[-1] = f"{joined[-1]} {current}".strip()
        else:
            joined.append(current)

    return joined


def _is_section_heading(tag: Tag) -> bool:
    return bool(tag.name and re.fullmatch(r"h\d", tag.name))


def _is_instruction_container(tag: Tag) -> bool:
    classes = " ".join(tag.get("class", []))
    return bool(_INSTRUCTION_CLASS.search(classes))


def _looks_like_instructions(ingredients: list[str]) -> bool:
    if not ingredients:
        return False

    long_items = sum(1 for item in ingredients if len(item) > 120)
    verb_items = sum(1 for item in ingredients if _INSTRUCTION_START.match(item))
    threshold = max(2, len(ingredients) // 2)
    return long_items >= threshold or verb_items >= threshold


def _extract_json_ld_cook_time_minutes(soup: BeautifulSoup) -> float | None:
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string or script.get_text()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        minutes = _recipe_time_from_json_ld(data)
        if minutes is not None:
            return minutes
    return None


def _recipe_time_from_json_ld(data: object) -> float | None:
    if isinstance(data, list):
        for item in data:
            minutes = _recipe_time_from_json_ld(item)
            if minutes is not None:
                return minutes
        return None

    if not isinstance(data, dict):
        return None

    recipe_type = data.get("@type", "")
    types = recipe_type if isinstance(recipe_type, list) else [recipe_type]
    if any(str(item).casefold() == "recipe" for item in types):
        total = _parse_iso8601_duration_minutes(data.get("totalTime"))
        if total is not None:
            return total

        cook = _parse_iso8601_duration_minutes(data.get("cookTime"))
        prep = _parse_iso8601_duration_minutes(data.get("prepTime"))
        if cook is not None and prep is not None:
            return cook + prep
        if cook is not None:
            return cook
        if prep is not None:
            return prep

    for key in ("@graph", "mainEntity"):
        nested = data.get(key)
        if nested is not None:
            minutes = _recipe_time_from_json_ld(nested)
            if minutes is not None:
                return minutes

    return None


_ISO8601_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
    re.IGNORECASE,
)


def _parse_iso8601_duration_minutes(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    match = _ISO8601_DURATION.match(text)
    if not match:
        return None

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    total = days * 24 * 60 + hours * 60 + minutes + seconds / 60
    return total if total > 0 else None


def _extract_json_ld_ingredients(soup: BeautifulSoup) -> list[str]:
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string or script.get_text()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        ingredients = _recipe_ingredients_from_json_ld(data)
        if ingredients:
            return ingredients
    return []


def _recipe_ingredients_from_json_ld(data: object) -> list[str]:
    if isinstance(data, list):
        for item in data:
            ingredients = _recipe_ingredients_from_json_ld(item)
            if ingredients:
                return ingredients
        return []

    if not isinstance(data, dict):
        return []

    recipe_type = data.get("@type", "")
    types = recipe_type if isinstance(recipe_type, list) else [recipe_type]
    if any(str(item).casefold() == "recipe" for item in types):
        raw_ingredients = data.get("recipeIngredient") or data.get("ingredients")
        if isinstance(raw_ingredients, list):
            cleaned = [
                str(item).replace("\n", " ").strip()
                for item in raw_ingredients
                if str(item).strip()
            ]
            if cleaned:
                return cleaned

    for key in ("@graph", "mainEntity"):
        nested = data.get(key)
        if nested is not None:
            ingredients = _recipe_ingredients_from_json_ld(nested)
            if ingredients:
                return ingredients

    return []


def ingredients_to_text(ingredients: list[str]) -> str:
    return "\n".join(ingredients)
