"""NYT Cooking integration — credentials, recipe box, and recipe JSON API."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from html import unescape
from typing import Any

import requests

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


class NytSyncCancelled(NYTCookingError):
    """User cancelled an interactive NYT sync step."""


@dataclass(frozen=True)
class NytCredentials:
    nyt_s_cookie: str
    regi_id: str


@dataclass(frozen=True)
class NytSavedRecipe:
    id: str
    name: str
    url: str
    author: str | None = None


@dataclass(frozen=True)
class NytCollection:
    id: str
    name: str
    recipe_count: int = 0


@dataclass(frozen=True)
class NytRecipe:
    id: str
    name: str
    url: str
    ingredients: list[str]
    author: str | None = None


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
    Raises ``NytSyncCancelled`` when the user declines or enters an invalid choice.
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
            raise NytSyncCancelled("Sync cancelled.")
        return None, "All saved recipes"

    total = _recipe_box_total_count(client)
    options: list[tuple[str | None, str, int | None]] = [
        (None, "All saved recipes", total),
    ]
    for collection in collections:
        options.append((collection.id, collection.name, collection.recipe_count))

    info("Choose a recipe-box folder to sync:")
    for index, (_collection_id, label, count) in enumerate(options, start=1):
        count_note = f" ({count} recipes)" if count is not None else ""
        info(f"  {index}. {label}{count_note}")

    while True:
        choice = prompt_fn("Folder [#]: ").strip()
        if not choice:
            raise NytSyncCancelled("Sync cancelled.")
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
class NytSyncSummary:
    total: int = 0
    skipped_existing: int = 0
    created: int = 0
    failed: int = 0
    dry_run: int = 0


def sync_saved_recipes_to_notion(
    db: Any,
    client: NYTCookingClient,
    *,
    collection_name: str | None = None,
    collection_id: str | None = None,
    collection_label: str | None = None,
    dry_run: bool = False,
    no_confirm: bool = False,
    confirm: Callable[[str], bool] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> NytSyncSummary:
    """Sync NYT saved recipes to Notion, skipping duplicates by link."""
    from src.grocery_wizard.recipes.add_recipe import add_prefetched_recipes

    summary = NytSyncSummary()
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
            if on_progress:
                on_progress(f"Would add: {saved.name}")
            continue

        try:
            recipe = client.get_recipe(saved.id)
        except NYTCookingError as exc:
            summary.failed += 1
            if on_progress:
                on_progress(f"Failed to fetch recipe '{saved.name}': {exc}")
            continue

        created_ids = add_prefetched_recipes(
            db,
            [(recipe.name, recipe.url, recipe.ingredients)],
            confirm=confirm,
            no_confirm=no_confirm,
        )
        if created_ids:
            summary.created += 1
            if on_progress:
                on_progress(f"Created: {recipe.name}")
        else:
            if on_progress:
                on_progress(f"Skipped: {recipe.name}")

    return summary


def _absolute_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{SITE}{url}"
    return url


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


def _parse_recipe_payload(payload: dict[str, Any]) -> NytRecipe:
    byline = payload.get("byline")
    author = byline.strip().title() if isinstance(byline, str) and byline else None
    return NytRecipe(
        id=str(payload.get("id", "")),
        name=_plain_text(payload.get("name", "")) or str(payload.get("name", "")),
        url=_absolute_url(str(payload.get("url", ""))),
        ingredients=_ingredients_from_parts(payload.get("parts")),
        author=author,
    )
