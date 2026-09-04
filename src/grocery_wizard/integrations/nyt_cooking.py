"""NYT Cooking integration — credentials, recipe box, and recipe JSON API."""

from __future__ import annotations

__all__ = [
    "NYTCookingClient",
    "NYTCookingError",
    "NytAuthError",
    "NytCollection",
    "NytCreatedRecipe",
    "NytCredentials",
    "NytNetworkError",
    "NytNotFoundError",
    "NytRecipe",
    "NytSavedRecipe",
    "NytSyncCancelledError",
    "NytSyncSummary",
    "load_credentials",
    "prompt_collection_choice",
    "sync_saved_recipes_to_notion",
]

import json
import os
import re
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import Any

import requests

from src.grocery_wizard.config import NYT_LAST_SYNC_PATH
from src.grocery_wizard.integrations.notion import DEFAULT_NYT_SYNCED_COLUMN

SITE = "https://cooking.nytimes.com"
API_HEADERS = {"x-cooking-api": "cooking-frontend", "accept": "*/*"}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30
DEFAULT_PER_PAGE = 48

_REGI_ID_PATTERN = re.compile(r"regi_id=(\d+)", re.IGNORECASE)
_HTML_TAGS = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


class NYTCookingError(Exception):
    """Base error for NYT Cooking access."""


class NytAuthError(NYTCookingError):
    """Credentials are missing or were rejected."""


class NytNotFoundError(NYTCookingError):
    """The requested resource does not exist."""


class NytNetworkError(NYTCookingError):
    """The request could not be completed."""


class NytSyncCancelledError(NYTCookingError):
    """User cancelled an interactive NYT sync step."""


@dataclass(frozen=True, slots=True)
class NytCredentials:
    nyt_s_cookie: str
    regi_id: str


@dataclass(frozen=True, slots=True)
class NytSavedRecipe:
    id: str
    name: str
    url: str
    author: str | None = None


@dataclass(frozen=True, slots=True)
class NytCollection:
    id: str
    name: str
    recipe_count: int = 0


@dataclass(frozen=True, slots=True)
class NytRecipe:
    id: str
    name: str
    url: str
    ingredients: list[str]
    author: str | None = None
    total_time_minutes: float | None = None
    prep_time_minutes: float | None = None
    cook_time_minutes: float | None = None


def parse_regi_id(value: str) -> str:
    """Extract regi_id from a raw id or full regi_cookie string."""
    stripped = value.strip()
    match = _REGI_ID_PATTERN.search(stripped)
    if match:
        return match.group(1)
    return stripped


def load_credentials() -> NytCredentials | None:
    """Load credentials from environment variables."""
    cookie = os.getenv("NYT_S_COOKIE", "").strip()
    regi_id = os.getenv("NYT_REGI_ID", "").strip() or os.getenv("NYT_USER_ID", "").strip()

    if cookie and regi_id:
        return NytCredentials(nyt_s_cookie=cookie, regi_id=regi_id)
    return None


def credentials_status() -> dict[str, Any]:
    """Return whether credentials are configured via environment variables."""
    creds = load_credentials()
    return {
        "configured": creds is not None,
        "regi_id": creds.regi_id if creds else None,
    }


class NYTCookingClient:
    """HTTP client for cooking.nytimes.com JSON endpoints."""

    def __init__(
        self,
        credentials: NytCredentials | None = None,
        *,
        session: requests.Session | None = None,
    ) -> None:
        self._credentials = credentials or load_credentials()
        self._http = session or requests.Session()
        self._http.headers["User-Agent"] = USER_AGENT
        if self._credentials:
            self._http.cookies.set(
                "NYT-S",
                self._credentials.nyt_s_cookie,
                domain=".nytimes.com",
            )

    @property
    def credentials(self) -> NytCredentials | None:
        return self._credentials

    def _require_credentials(self) -> NytCredentials:
        if self._credentials is None:
            raise NytAuthError(
                "NYT Cooking credentials are not configured. Set NYT_S_COOKIE and "
                "NYT_REGI_ID (or NYT_USER_ID) in your environment."
            )
        return self._credentials

    def _get(self, url: str, **kwargs: Any) -> requests.Response:
        try:
            response = self._http.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            raise NytNetworkError(str(exc)) from exc

        if response.status_code in (401, 403):
            raise NytAuthError(
                "NYT Cooking rejected the request — cookie missing, invalid, or expired."
            )
        if response.status_code == 404:
            raise NytNotFoundError(f"Nothing found at {url}.")
        if not response.ok:
            raise NytNetworkError(f"NYT Cooking returned HTTP {response.status_code}.")
        return response

    def _json(self, response: requests.Response, what: str) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise NytNetworkError(f"{what} response was not valid JSON.") from exc
        if not isinstance(data, dict):
            raise NytNetworkError(f"{what} response was not a JSON object.")
        return data

    def verify_auth(self) -> bool:
        """Verify credentials by fetching the first page of the recipe box."""
        self._require_credentials()
        self.list_saved_recipes(page=1, per_page=1)
        return True

    def list_collections(self) -> list[NytCollection]:
        """List recipe-box folders/collections for the signed-in user."""
        self._require_credentials()
        response = self._get(
            f"{SITE}/api/v5/users/me/collections",
            params={"sort": "alphanumeric", "per_page": 9999},
            headers=API_HEADERS,
        )
        payload = self._json(response, "Collections")
        collections = payload.get("collections") or []
        results: list[NytCollection] = []
        for item in collections:
            if not isinstance(item, dict):
                continue
            results.append(
                NytCollection(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    recipe_count=int(item.get("collectables_count") or 0),
                )
            )
        return results

    def find_collection_by_name(self, name: str) -> NytCollection | None:
        """Case-insensitive match on folder/collection name."""
        target = name.strip().casefold()
        for collection in self.list_collections():
            if collection.name.casefold() == target:
                return collection
        return None

    def list_saved_recipes(
        self,
        *,
        page: int = 1,
        per_page: int = DEFAULT_PER_PAGE,
        collection_id: str | None = None,
    ) -> dict[str, Any]:
        """Return one page of saved recipes from the recipe box."""
        creds = self._require_credentials()
        params: dict[str, str | int] = {
            "q": "",
            "page": page,
            "per_page": per_page,
        }
        if collection_id:
            params["collection_id"] = collection_id

        response = self._get(
            f"{SITE}/api/v2/users/{creds.regi_id}/search/recipe_box_search",
            params=params,
            headers=API_HEADERS,
        )
        return self._json(response, "Recipe box")

    def iter_all_saved_recipes(
        self,
        *,
        collection_id: str | None = None,
        per_page: int = DEFAULT_PER_PAGE,
    ) -> Iterator[NytSavedRecipe]:
        """Yield every saved recipe, paging through the recipe box."""
        page = 1
        while True:
            payload = self.list_saved_recipes(
                page=page,
                per_page=per_page,
                collection_id=collection_id,
            )
            items = payload.get("collectables") or []
            for item in items:
                if not isinstance(item, dict):
                    continue
                yield NytSavedRecipe(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    url=_absolute_url(str(item.get("url", ""))),
                    author=item.get("byline"),
                )

            total = int(payload.get("collectables_count") or 0)
            if page * per_page >= total or not items:
                break
            page += 1

    def get_recipe(self, recipe_id: str) -> NytRecipe:
        """Fetch full recipe details from the JSON recipe endpoint."""
        response = self._get(
            f"{SITE}/api/v2/recipes/{recipe_id}",
            headers=API_HEADERS,
        )
        payload = self._json(response, "Recipe")
        return _parse_recipe_payload(payload)

    def get_recipe_by_url(self, url: str) -> NytRecipe:
        """Fetch recipe details using an id parsed from a cooking.nytimes.com URL."""
        recipe_id = _recipe_id_from_url(url)
        if not recipe_id:
            raise NytNotFoundError(f"Could not parse NYT recipe id from URL: {url}")
        recipe = self.get_recipe(recipe_id)
        if recipe.url:
            return recipe
        return NytRecipe(
            id=recipe.id,
            name=recipe.name,
            url=url,
            ingredients=recipe.ingredients,
            author=recipe.author,
        )


def _recipe_box_total_count(client: NYTCookingClient) -> int | None:
    try:
        payload = client.list_saved_recipes(page=1, per_page=1)
    except NYTCookingError:
        return None
    return int(payload.get("collectables_count") or 0)


def prompt_collection_choice(
    client: NYTCookingClient,
    *,
    prompt_fn: Callable[[str], str] = input,
    on_info: Callable[[str], None] | None = None,
) -> tuple[str | None, str]:
    """Interactively pick a recipe-box collection.

    Returns ``(collection_id, label)``. ``collection_id`` is ``None`` for the full recipe box.
    Raises ``NytSyncCancelledError`` when the user declines or enters an invalid choice.
    """
    from src.grocery_wizard.lib.prompts import confirm_yes_default

    info = on_info or (lambda _message: None)

    collections: list[NytCollection] = []
    try:
        collections = client.list_collections()
    except NytAuthError:
        raise
    except NYTCookingError as exc:
        info(f"Could not load recipe-box folders ({exc}); full recipe box only.")

    if not collections:
        total = _recipe_box_total_count(client)
        count_note = f" ({total} recipes)" if total is not None else ""
        info(f"Syncing full recipe box{count_note}.")
        if not confirm_yes_default("Continue?", prompt_fn=prompt_fn):
            raise NytSyncCancelledError("Sync cancelled.")
        return None, "All saved recipes"

    total = _recipe_box_total_count(client)
    options: list[tuple[str | None, str, int | None]] = [
        (None, "All saved recipes", total),
        *((c.id, c.name, c.recipe_count) for c in collections),
    ]

    info("Choose a recipe-box folder to sync:")
    for index, (_collection_id, label, count) in enumerate(options, start=1):
        count_note = f" ({count} recipes)" if count is not None else ""
        info(f"  {index}. {label}{count_note}")

    while True:
        choice = prompt_fn("Folder [#]: ").strip()
        if not choice:
            raise NytSyncCancelledError("Sync cancelled.")
        try:
            picked = int(choice)
        except ValueError:
            info("Enter a number from the list.")
            continue
        if 1 <= picked <= len(options):
            collection_id, label, _count = options[picked - 1]
            return collection_id, label
        info(f"Enter a number between 1 and {len(options)}.")


@dataclass
class NytCreatedRecipe:
    page_id: str
    name: str
    url: str
    metadata: dict[str, Any]
    flags: list[str] = field(default_factory=list)


@dataclass
class NytSyncSummary:
    total: int = 0
    skipped_existing: int = 0
    created: int = 0
    failed: int = 0
    dry_run: int = 0
    collection_label: str | None = None
    created_recipes: list[NytCreatedRecipe] = field(default_factory=list)


def sync_saved_recipes_to_notion(
    db: Any,
    client: NYTCookingClient,
    *,
    collection_name: str | None = None,
    collection_id: str | None = None,
    collection_label: str | None = None,
    dry_run: bool = False,
    no_confirm: bool = True,
    confirm: Callable[[str], bool] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> NytSyncSummary:
    """Sync NYT saved recipes to Notion, skipping duplicates by link."""
    from src.grocery_wizard.recipes.add_recipe import add_prefetched_recipes

    resolved_id = collection_id
    resolved_label = collection_label

    if resolved_id is None and collection_name:
        collection = client.find_collection_by_name(collection_name)
        if collection is None:
            if on_progress:
                on_progress(
                    f"Collection '{collection_name}' not found; syncing full recipe box."
                )
        else:
            resolved_id = collection.id
            resolved_label = collection.name
            if on_progress:
                on_progress(
                    f"Syncing collection: {collection.name} ({collection.recipe_count} recipes)"
                )
    elif on_progress and resolved_label:
        if resolved_id is not None:
            on_progress(f"Syncing collection: {resolved_label}")
        else:
            total = _recipe_box_total_count(client)
            count_note = f" ({total} recipes)" if total is not None else ""
            on_progress(f"Syncing: {resolved_label}{count_note}")

    summary = NytSyncSummary(collection_label=resolved_label)

    nyt_column = db.nyt_synced_column_name()
    if on_progress:
        if nyt_column:
            on_progress(f"Marking synced recipes with checkbox: {nyt_column}")
        else:
            on_progress(
                f"Warning: checkbox column '{DEFAULT_NYT_SYNCED_COLUMN}' "
                "not found in Notion — add it to tag NYT imports."
            )

    for saved in client.iter_all_saved_recipes(collection_id=resolved_id):
        summary.total += 1
        url = saved.url
        if not url:
            summary.failed += 1
            if on_progress:
                on_progress(f"Skipping recipe without URL: {saved.name}")
            continue

        existing = db.find_by_link(url)
        if existing:
            summary.skipped_existing += 1
            if on_progress:
                on_progress(f"Skip (already in Notion): {existing.name}")
            continue

        if dry_run:
            summary.dry_run += 1
            total_minutes = _fetch_nyt_total_minutes(client, saved.id, saved.url)
            metadata = _metadata_for_recipe(
                db,
                saved.name,
                url,
                mark_nyt_synced=True,
                total_minutes=total_minutes,
            )
            flags = flag_metadata_issues(saved.name, metadata)
            summary.created_recipes.append(
                NytCreatedRecipe(
                    page_id="",
                    name=saved.name,
                    url=url,
                    metadata=metadata,
                    flags=flags,
                )
            )
            if on_progress:
                on_progress(f"Would add: {saved.name}")
            continue

        total_minutes = _fetch_nyt_total_minutes(client, saved.id, saved.url)
        results = add_prefetched_recipes(
            db,
            [(saved.name, url, [], total_minutes)],
            confirm=confirm,
            no_confirm=no_confirm,
            include_ingredients=False,
            mark_nyt_synced=True,
        )
        if results:
            summary.created += 1
            result = results[0]
            metadata = _metadata_from_field_values(db, result.field_values)
            flags = flag_metadata_issues(result.name, metadata)
            entry = NytCreatedRecipe(
                page_id=result.page_id,
                name=result.name,
                url=result.url,
                metadata=metadata,
                flags=flags,
            )
            summary.created_recipes.append(entry)
            if on_progress:
                flag_note = f" [{'; '.join(flags)}]" if flags else ""
                on_progress(f"Created: {result.name}{flag_note}")
        elif on_progress:
            on_progress(f"Skipped: {saved.name}")

    return summary


_TITLE_MEAL_HINTS: dict[str, list[str]] = {
    "Dessert": ["cake", "cookie", "brownie", "pie", "pudding", "tart", "muffin"],
    "Breakfast": ["pancake", "waffle", "oatmeal", "frittata", "omelet", "omelette"],
    "Drink": ["smoothie", "cocktail", "lemonade", "limeade", "mocktail"],
    "Lunch": ["sandwich"],
    "Snack/Side": ["salad"],
}


def _metadata_for_recipe(
    db: Any,
    title: str,
    url: str,
    *,
    mark_nyt_synced: bool = False,
    total_minutes: float | None = None,
) -> dict[str, Any]:
    from src.grocery_wizard.recipes.classify import classify_recipe
    from src.grocery_wizard.recipes.weeknight import DEFAULT_WEEKNIGHT_COLUMN

    filter_columns = [(col.name, col.type, col.options) for col in db.schema.filter_columns]
    weeknight_column = (
        DEFAULT_WEEKNIGHT_COLUMN
        if DEFAULT_WEEKNIGHT_COLUMN in db.schema.all_columns
        else None
    )
    inferred = classify_recipe(
        title,
        [],
        filter_columns,
        total_minutes=total_minutes,
        weeknight_column=weeknight_column,
    )
    metadata: dict[str, Any] = {
        db.schema.name_column: title,
        db.schema.link_column: url,
    }
    metadata.update(inferred)
    if mark_nyt_synced:
        nyt_column = db.nyt_synced_column_name()
        if nyt_column:
            metadata[nyt_column] = True
    return _metadata_from_field_values(db, metadata)


def _metadata_from_field_values(db: Any, field_values: dict[str, Any]) -> dict[str, Any]:
    schema = db.schema
    skip = {schema.name_column, schema.link_column}
    if schema.ingredients_column:
        skip.add(schema.ingredients_column)
    return {
        key: value
        for key, value in field_values.items()
        if key not in skip and value not in (None, "", [])
    }


def flag_metadata_issues(name: str, metadata: dict[str, Any]) -> list[str]:
    """Return human-readable flags when title and assigned metadata look inconsistent."""
    title = name.lower()
    meal = metadata.get("Meal")
    if isinstance(meal, str):
        for suggested_meal, keywords in _TITLE_MEAL_HINTS.items():
            if any(keyword in title for keyword in keywords) and meal != suggested_meal:
                return [f"title suggests {suggested_meal} but Meal={meal}"]
    missing = [column for column, value in metadata.items() if value in (None, "", [])]
    if len(missing) >= 2:
        return [f"missing metadata: {', '.join(sorted(missing))}"]
    return []


def save_sync_report(summary: NytSyncSummary, path: Path = NYT_LAST_SYNC_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "synced_at": datetime.now(UTC).isoformat(),
        "collection": summary.collection_label,
        "created": [asdict(recipe) for recipe in summary.created_recipes],
        "counts": {
            "total": summary.total,
            "skipped_existing": summary.skipped_existing,
            "created": summary.created,
            "dry_run": summary.dry_run,
            "failed": summary.failed,
        },
    }
    path.write_text(json.dumps(payload, indent=2))


def load_sync_report(path: Path = NYT_LAST_SYNC_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def format_metadata_review(report: dict[str, Any]) -> str:
    lines: list[str] = []
    collection = report.get("collection") or "recipe box"
    lines.append(f"NYT sync review — {collection}")
    lines.append(f"Synced at: {report.get('synced_at', 'unknown')}")
    lines.append("")

    created = report.get("created", [])
    if not created:
        lines.append("No recipes to review.")
        return "\n".join(lines)

    for index, recipe in enumerate(created, start=1):
        lines.append(f"{index}. {recipe.get('name', '?')}")
        metadata = recipe.get("metadata", {})
        if metadata:
            for key, value in sorted(metadata.items()):
                lines.append(f"   {key}: {value}")
        flags = recipe.get("flags") or []
        if flags:
            lines.append(f"   ⚠ {flags[0]}")
        lines.append("")

    flagged = sum(1 for recipe in created if recipe.get("flags"))
    lines.append(f"{len(created)} recipe(s), {flagged} flagged for review.")
    return "\n".join(lines)


@dataclass
class NytReclassifyChange:
    page_id: str
    name: str
    field: str
    old_value: Any
    new_value: Any


@dataclass
class NytReclassifySummary:
    total: int = 0
    meal_changes: int = 0
    weeknight_set: int = 0
    weeknight_cleared: int = 0
    unchanged: int = 0
    api_failures: int = 0
    changes: list[NytReclassifyChange] = field(default_factory=list)


def reclassify_nyt_synced_recipes(
    db: Any,
    client: NYTCookingClient,
    *,
    dry_run: bool = False,
    on_progress: Callable[[str], None] | None = None,
) -> NytReclassifySummary:
    """Re-run Meal and Weeknight Friendly for NYT-synced recipes in Notion."""
    from src.grocery_wizard.recipes.classify import classify_recipe
    from src.grocery_wizard.recipes.weeknight import DEFAULT_WEEKNIGHT_COLUMN, is_weeknight_friendly

    nyt_column = db.nyt_synced_column_name()
    if not nyt_column:
        raise NYTCookingError(
            f"NYT synced checkbox column not found. Add '{DEFAULT_NYT_SYNCED_COLUMN}' to Notion."
        )

    weeknight_column = DEFAULT_WEEKNIGHT_COLUMN
    if weeknight_column not in db.schema.all_columns:
        weeknight_column = ""

    filter_columns = [(col.name, col.type, col.options) for col in db.schema.filter_columns]
    summary = NytReclassifySummary()

    for recipe in db.query_recipes():
        if not recipe.properties.get(nyt_column):
            continue

        summary.total += 1
        title = recipe.name
        inferred = classify_recipe(title, [], filter_columns)
        new_meal = inferred.get("Meal")
        old_meal = recipe.properties.get("Meal")

        total_minutes: float | None = None
        recipe_id = _recipe_id_from_url(recipe.link or "")
        if recipe_id:
            try:
                nyt_recipe = client.get_recipe(recipe_id)
                total_minutes = nyt_recipe.total_time_minutes
            except NYTCookingError:
                summary.api_failures += 1
                if on_progress:
                    on_progress(f"Could not fetch NYT timing for: {title}")

        fields: dict[str, Any] = {}

        if new_meal and new_meal != old_meal:
            fields["Meal"] = new_meal
            summary.meal_changes += 1
            summary.changes.append(
                NytReclassifyChange(
                    page_id=recipe.page_id,
                    name=title,
                    field="Meal",
                    old_value=old_meal,
                    new_value=new_meal,
                )
            )

        effective_meal = fields.get("Meal", old_meal)
        if weeknight_column:
            new_weeknight = is_weeknight_friendly(
                title,
                meal=effective_meal,
                total_minutes=total_minutes,
            )
            old_weeknight = bool(recipe.properties.get(weeknight_column))
            if new_weeknight != old_weeknight:
                fields[weeknight_column] = new_weeknight
                if new_weeknight:
                    summary.weeknight_set += 1
                else:
                    summary.weeknight_cleared += 1
                summary.changes.append(
                    NytReclassifyChange(
                        page_id=recipe.page_id,
                        name=title,
                        field=weeknight_column,
                        old_value=old_weeknight,
                        new_value=new_weeknight,
                    )
                )

        if fields:
            if on_progress:
                detail = ", ".join(f"{key}={value}" for key, value in fields.items())
                on_progress(f"Update: {title} ({detail})")
            if not dry_run:
                db.update_recipe(recipe.page_id, fields)
        else:
            summary.unchanged += 1

    return summary


def format_reclassify_summary(summary: NytReclassifySummary) -> str:
    lines = [
        f"NYT reclassify — {summary.total} recipe(s)",
        f"Meal changes: {summary.meal_changes}",
        f"Weeknight friendly set: {summary.weeknight_set}",
        f"Weeknight friendly cleared: {summary.weeknight_cleared}",
        f"Unchanged: {summary.unchanged}",
    ]
    if summary.api_failures:
        lines.append(f"NYT API timing failures: {summary.api_failures}")

    notable = [change for change in summary.changes if change.field == "Meal"]
    if notable:
        lines.append("")
        lines.append("Meal corrections:")
        lines.extend(
            f"  {change.name}: {change.old_value} -> {change.new_value}"
            for change in notable[:30]
        )
        if len(notable) > 30:
            lines.append(f"  ... and {len(notable) - 30} more")

    return "\n".join(lines)


def apply_metadata_corrections(
    db: Any,
    corrections: list[dict[str, Any]],
) -> int:
    """Apply metadata updates. Each item: ``{"page_id": "...", "fields": {...}}``."""
    updated = 0
    for item in corrections:
        page_id = item.get("page_id")
        fields = item.get("fields")
        if not page_id or not fields:
            continue
        db.update_recipe(page_id, fields)
        updated += 1
    return updated


def _absolute_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{SITE}{url}"
    return url


def _fetch_nyt_total_minutes(
    client: NYTCookingClient,
    recipe_id: str,
    url: str,
) -> float | None:
    resolved_id = recipe_id or _recipe_id_from_url(url) or ""
    if not resolved_id:
        return None
    try:
        return client.get_recipe(resolved_id).total_time_minutes
    except NYTCookingError:
        return None


def _recipe_id_from_url(url: str) -> str | None:
    match = re.search(r"/recipes/(\d+)", url)
    return match.group(1) if match else None


def _plain_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _WHITESPACE.sub(" ", unescape(_HTML_TAGS.sub(" ", value))).strip()


def _ingredients_from_parts(parts: Any) -> list[str]:
    lines: list[str] = []
    if not isinstance(parts, list):
        return lines
    for group in parts:
        if not isinstance(group, dict):
            continue
        for item in group.get("ingredients", []):
            if not isinstance(item, dict):
                continue
            quantity = str(item.get("display_quantity") or "").strip()
            text = _plain_text(item.get("display_text", ""))
            line = f"{quantity} {text}".strip()
            if line:
                lines.append(line)
    return lines


def _parse_minutes(value: Any) -> float | None:
    if not isinstance(value, dict):
        return None
    minutes = value.get("minutes")
    if minutes is None:
        return None
    try:
        return float(minutes)
    except (TypeError, ValueError):
        return None


def _parse_recipe_payload(payload: dict[str, Any]) -> NytRecipe:
    byline = payload.get("byline")
    author = byline.strip().title() if isinstance(byline, str) and byline else None
    return NytRecipe(
        id=str(payload.get("id", "")),
        name=_plain_text(payload.get("name", "")) or str(payload.get("name", "")),
        url=_absolute_url(str(payload.get("url", ""))),
        ingredients=_ingredients_from_parts(payload.get("parts")),
        author=author,
        total_time_minutes=_parse_minutes(payload.get("cooking_time")),
        prep_time_minutes=_parse_minutes(payload.get("prep_time")),
        cook_time_minutes=_parse_minutes(payload.get("cook_time")),
    )
