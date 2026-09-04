"""Store aisle ordering and ingredient classification for grocery lists."""

from __future__ import annotations

__all__ = [
    "StoreAisleConfig",
    "group_grocery_items_by_aisle",
    "ingredient_name",
    "load_store_aisles",
    "sort_grocery_items",
]

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from src.grocery_wizard.config import STORE_AISLES_PATH
from src.grocery_wizard.ingredients.normalize import parse_amount

_SECTION_HEADER_RE = re.compile(r"^#\s*---\s*(?P<id>.+?)(?::\s*(?P<label>.+?))?\s*---\s*$")


@dataclass(frozen=True, slots=True)
class StoreAisleConfig:
    aisle_order: tuple[str, ...]
    aisle_labels: dict[str, str]
    aisle_keywords: dict[str, tuple[str, ...]]


def parse_store_aisles_file(path: Path) -> StoreAisleConfig:
    """Parse store aisle order, labels, and keywords from a config file."""
    aisle_order: list[str] = []
    aisle_labels: dict[str, str] = {}
    aisle_keywords: dict[str, list[str]] = {}
    current_aisle: str | None = None

    if not path.exists():
        return StoreAisleConfig((), {}, {})

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        header_match = _SECTION_HEADER_RE.match(stripped)
        if header_match:
            aisle_id = header_match.group("id").strip().lower()
            label = (header_match.group("label") or aisle_id).strip()
            aisle_order.append(aisle_id)
            aisle_labels[aisle_id] = label
            aisle_keywords[aisle_id] = []
            current_aisle = aisle_id
            continue

        if stripped.startswith("#") or current_aisle is None:
            continue

        aisle_keywords[current_aisle].append(stripped.lower())

    if "other" not in aisle_order:
        aisle_order.append("other")
        aisle_labels.setdefault("other", "Other")
        aisle_keywords.setdefault("other", [])

    return StoreAisleConfig(
        aisle_order=tuple(aisle_order),
        aisle_labels=aisle_labels,
        aisle_keywords={aisle: tuple(words) for aisle, words in aisle_keywords.items()},
    )


_aisle_config_cache: dict[str, tuple[tuple[int, int], StoreAisleConfig]] = {}


def load_store_aisles(path: str | None = None) -> StoreAisleConfig:
    """Load store aisle config from the committed config file."""
    resolved = Path(path) if path else STORE_AISLES_PATH
    cache_key = str(resolved.resolve())
    if resolved.exists():
        stat = resolved.stat()
        cache_stamp = (stat.st_mtime_ns, stat.st_size)
    else:
        cache_stamp = (-1, -1)
    cached = _aisle_config_cache.get(cache_key)
    if cached is not None and cached[0] == cache_stamp:
        return cached[1]

    if not resolved.exists():
        print(
            f"Warning: store aisle config not found ({resolved}); items will appear under Other.",
            file=sys.stderr,
        )

    config = parse_store_aisles_file(resolved)
    _aisle_config_cache[cache_key] = (cache_stamp, config)
    return config


def ingredient_name(item: str) -> str:
    """Return the ingredient name from a display line, stripping any amount prefix."""
    name, _amount = parse_amount(item)
    return name or item.strip()


def classify_aisle(item: str, *, config: StoreAisleConfig | None = None) -> str:
    """Classify a grocery list item into a store aisle."""
    cfg = config or load_store_aisles()
    name = ingredient_name(item).lower()
    if not name:
        return "other"

    name_words = name.split()
    best_aisle = "other"
    best_keyword_len = 0
    best_aisle_rank = len(cfg.aisle_order)

    for rank, aisle in enumerate(cfg.aisle_order):
        if aisle == "other":
            continue
        for keyword in cfg.aisle_keywords.get(aisle, ()):
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


def sort_grocery_items(
    items: list[str],
    *,
    config: StoreAisleConfig | None = None,
) -> list[str]:
    """Sort grocery items by store walk order, then alphabetically within each aisle."""
    cfg = config or load_store_aisles()
    aisle_rank = {aisle: index for index, aisle in enumerate(cfg.aisle_order)}

    def sort_key(item: str) -> tuple[int, str]:
        aisle = classify_aisle(item, config=cfg)
        return aisle_rank.get(aisle, len(cfg.aisle_order)), item.lower()

    return sorted(items, key=sort_key)


def group_grocery_items_by_aisle(
    items: list[str],
    *,
    config: StoreAisleConfig | None = None,
) -> list[tuple[str, list[str]]]:
    """Group sorted grocery items by aisle, omitting empty aisles."""
    cfg = config or load_store_aisles()
    sorted_items = sort_grocery_items(items, config=cfg)
    groups: list[tuple[str, list[str]]] = []
    current_aisle: str | None = None
    current_items: list[str] = []

    for item in sorted_items:
        aisle = classify_aisle(item, config=cfg)
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


def aisle_label(aisle: str, *, config: StoreAisleConfig | None = None) -> str:
    cfg = config or load_store_aisles()
    return cfg.aisle_labels.get(aisle, aisle.title())


def _contains_word_phrase(haystack_words: list[str], needle_words: list[str]) -> bool:
    if not needle_words or len(needle_words) > len(haystack_words):
        return False
    width = len(needle_words)
    for index in range(len(haystack_words) - width + 1):
        if all(
            _word_matches(haystack_words[index + offset], needle_words[offset])
            for offset in range(width)
        ):
            return True
    return False


def _word_matches(haystack_word: str, needle_word: str) -> bool:
    if haystack_word == needle_word:
        return True
    if haystack_word == needle_word + "s":
        return True
    if haystack_word == needle_word + "es":
        return True
    return needle_word.endswith("y") and haystack_word == needle_word[:-1] + "ies"
