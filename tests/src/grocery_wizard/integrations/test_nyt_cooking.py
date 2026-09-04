"""Tests for NYT Cooking integration with mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.grocery_wizard.integrations.nyt_cooking import (
    NytAuthError,
    NytCollection,
    NYTCookingClient,
    NytCredentials,
    NytSyncCancelled,
    _ingredients_from_parts,
    _parse_recipe_payload,
    credentials_status,
    load_credentials,
    parse_regi_id,
    prompt_collection_choice,
    sync_saved_recipes_to_notion,
)


@pytest.fixture
def credentials() -> NytCredentials:
    return NytCredentials(nyt_s_cookie="test-cookie", regi_id="12345678")


@pytest.fixture
def env_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NYT_S_COOKIE", "test-cookie")
    monkeypatch.setenv("NYT_REGI_ID", "12345678")


def test_parse_regi_id_from_cookie() -> None:
    assert parse_regi_id("regi_id=87654321; other=value") == "87654321"
    assert parse_regi_id("87654321") == "87654321"


def test_load_credentials_from_env(env_credentials: None) -> None:
    loaded = load_credentials()
    assert loaded == NytCredentials(nyt_s_cookie="test-cookie", regi_id="12345678")


def test_load_credentials_accepts_nyt_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NYT_S_COOKIE", "test-cookie")
    monkeypatch.setenv("NYT_USER_ID", "87654321")
    monkeypatch.delenv("NYT_REGI_ID", raising=False)

    loaded = load_credentials()
    assert loaded == NytCredentials(nyt_s_cookie="test-cookie", regi_id="87654321")


def test_load_credentials_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NYT_S_COOKIE", raising=False)
    monkeypatch.delenv("NYT_REGI_ID", raising=False)
    monkeypatch.delenv("NYT_USER_ID", raising=False)

    assert load_credentials() is None


def test_credentials_status_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NYT_S_COOKIE", raising=False)
    monkeypatch.delenv("NYT_REGI_ID", raising=False)
    monkeypatch.delenv("NYT_USER_ID", raising=False)

    status = credentials_status()
    assert status["configured"] is False


def test_credentials_status_configured(env_credentials: None) -> None:
    status = credentials_status()
    assert status["configured"] is True
    assert status["regi_id"] == "12345678"


def test_ingredients_from_parts() -> None:
    parts = [
        {
            "ingredients": [
                {"display_quantity": "1 cup", "display_text": "flour"},
                {"display_quantity": "", "display_text": "salt"},
            ]
        }
    ]
    assert _ingredients_from_parts(parts) == ["1 cup flour", "salt"]


def test_parse_recipe_payload() -> None:
    recipe = _parse_recipe_payload(
        {
            "id": 1019049,
            "name": "Simple Pasta",
            "url": "/recipes/1019049-simple-pasta",
            "byline": "sam sifton",
            "parts": [
                {"ingredients": [{"display_quantity": "8 oz", "display_text": "spaghetti"}]}
            ],
        }
    )
    assert recipe.id == "1019049"
    assert recipe.name == "Simple Pasta"
    assert recipe.url == "https://cooking.nytimes.com/recipes/1019049-simple-pasta"
    assert recipe.author == "Sam Sifton"
    assert recipe.ingredients == ["8 oz spaghetti"]


def _mock_response(
    *,
    status_code: int = 200,
    payload: dict | None = None,
    text: str = "",
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 300
    response.text = text
    if payload is not None:
        response.json.return_value = payload
    return response


def test_list_saved_recipes_pagination(credentials: NytCredentials) -> None:
    session = MagicMock()
    client = NYTCookingClient(credentials, session=session)

    session.get.side_effect = [
        _mock_response(
            payload={
                "collectables": [
                    {"id": "1", "name": "Recipe A", "url": "/recipes/1-a", "byline": "Author"},
                ],
                "collectables_count": 2,
            }
        ),
        _mock_response(
            payload={
                "collectables": [
                    {"id": "2", "name": "Recipe B", "url": "/recipes/2-b", "byline": None},
                ],
                "collectables_count": 2,
            }
        ),
    ]

    recipes = list(client.iter_all_saved_recipes(per_page=1))
    assert len(recipes) == 2
    assert recipes[0].name == "Recipe A"
    assert recipes[1].url == "https://cooking.nytimes.com/recipes/2-b"


def test_list_collections(credentials: NytCredentials) -> None:
    session = MagicMock()
    client = NYTCookingClient(credentials, session=session)
    session.get.return_value = _mock_response(
        payload={
            "collections": [
                {"id": 10, "name": "Weeknight", "collectables_count": 3},
                {"id": 11, "name": "Desserts", "collectables_count": 1},
            ]
        }
    )

    collections = client.list_collections()
    assert len(collections) == 2
    assert collections[0].name == "Weeknight"


def test_find_collection_by_name_case_insensitive(credentials: NytCredentials) -> None:
    session = MagicMock()
    client = NYTCookingClient(credentials, session=session)
    session.get.return_value = _mock_response(
        payload={"collections": [{"id": 10, "name": "Weeknight", "collectables_count": 3}]}
    )

    found = client.find_collection_by_name("weeknight")
    assert found is not None
    assert found.id == "10"


def test_get_recipe(credentials: NytCredentials) -> None:
    session = MagicMock()
    client = NYTCookingClient(credentials, session=session)
    session.get.return_value = _mock_response(
        payload={
            "id": 99,
            "name": "Soup",
            "url": "/recipes/99-soup",
            "parts": [{"ingredients": [{"display_quantity": "2 cups", "display_text": "broth"}]}],
        }
    )

    recipe = client.get_recipe("99")
    assert recipe.ingredients == ["2 cups broth"]


def test_verify_auth_rejects_401(credentials: NytCredentials) -> None:
    session = MagicMock()
    client = NYTCookingClient(credentials, session=session)
    session.get.return_value = _mock_response(status_code=401)

    with pytest.raises(NytAuthError):
        client.verify_auth()


def test_missing_credentials_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NYT_S_COOKIE", raising=False)
    monkeypatch.delenv("NYT_REGI_ID", raising=False)
    monkeypatch.delenv("NYT_USER_ID", raising=False)
    client = NYTCookingClient(None)
    with pytest.raises(NytAuthError):
        client.list_saved_recipes()


def test_sync_dry_run_skips_notion_writes(credentials: NytCredentials) -> None:
    session = MagicMock()
    client = NYTCookingClient(credentials, session=session)
    session.get.return_value = _mock_response(
        payload={
            "collectables": [
                {
                    "id": "1",
                    "name": "New Recipe",
                    "url": "https://cooking.nytimes.com/recipes/1-new",
                }
            ],
            "collectables_count": 1,
        }
    )

    db = MagicMock()
    db.find_by_link.return_value = None

    with patch("src.grocery_wizard.recipes.add_recipe.add_prefetched_recipes") as add_mock:
        summary = sync_saved_recipes_to_notion(db, client, dry_run=True)

    assert summary.total == 1
    assert summary.dry_run == 1
    assert summary.created == 0
    add_mock.assert_not_called()


def test_sync_skips_existing_links(credentials: NytCredentials) -> None:
    session = MagicMock()
    client = NYTCookingClient(credentials, session=session)
    session.get.return_value = _mock_response(
        payload={
            "collectables": [
                {
                    "id": "1",
                    "name": "Existing",
                    "url": "https://cooking.nytimes.com/recipes/1-existing",
                }
            ],
            "collectables_count": 1,
        }
    )

    db = MagicMock()
    db.find_by_link.return_value = MagicMock(name="Already There")

    with patch("src.grocery_wizard.recipes.add_recipe.add_prefetched_recipes") as add_mock:
        summary = sync_saved_recipes_to_notion(db, client)

    assert summary.skipped_existing == 1
    add_mock.assert_not_called()


def test_sync_creates_missing_recipes(credentials: NytCredentials) -> None:
    session = MagicMock()
    client = NYTCookingClient(credentials, session=session)

    def fake_get(url: str, **kwargs: object) -> MagicMock:
        if "recipe_box_search" in url:
            return _mock_response(
                payload={
                    "collectables": [
                        {
                            "id": "42",
                            "name": "Fresh Recipe",
                            "url": "https://cooking.nytimes.com/recipes/42-fresh",
                        }
                    ],
                    "collectables_count": 1,
                }
            )
        if "/recipes/42" in url:
            return _mock_response(
                payload={
                    "id": 42,
                    "name": "Fresh Recipe",
                    "url": "https://cooking.nytimes.com/recipes/42-fresh",
                    "parts": [
                        {"ingredients": [{"display_quantity": "1", "display_text": "egg"}]}
                    ],
                }
            )
        raise AssertionError(f"Unexpected URL: {url}")

    session.get.side_effect = fake_get

    db = MagicMock()
    db.find_by_link.return_value = None

    with patch(
        "src.grocery_wizard.recipes.add_recipe.add_prefetched_recipes",
        return_value=["page-1"],
    ) as add_mock:
        summary = sync_saved_recipes_to_notion(db, client, no_confirm=True)

    assert summary.created == 1
    add_mock.assert_called_once()
    args = add_mock.call_args[0]
    assert args[1][0][0] == "Fresh Recipe"


def test_prompt_collection_choice_picks_folder(credentials: NytCredentials) -> None:
    session = MagicMock()
    client = NYTCookingClient(credentials, session=session)

    def fake_get(url: str, **kwargs: object) -> MagicMock:
        if "collections" in url:
            return _mock_response(
                payload={
                    "collections": [
                        {"id": 10, "name": "Weeknight", "collectables_count": 3},
                        {"id": 11, "name": "Desserts", "collectables_count": 1},
                    ]
                }
            )
        if "recipe_box_search" in url:
            return _mock_response(payload={"collectables": [], "collectables_count": 12})
        raise AssertionError(f"Unexpected URL: {url}")

    session.get.side_effect = fake_get
    prompts = iter(["3"])
    collection_id, label = prompt_collection_choice(
        client,
        prompt_fn=lambda _msg: next(prompts),
    )

    assert collection_id == "11"
    assert label == "Desserts"


def test_prompt_collection_choice_picks_all_saved(credentials: NytCredentials) -> None:
    session = MagicMock()
    client = NYTCookingClient(credentials, session=session)

    def fake_get(url: str, **kwargs: object) -> MagicMock:
        if "collections" in url:
            return _mock_response(
                payload={
                    "collections": [
                        {"id": 10, "name": "Weeknight", "collectables_count": 3},
                    ]
                }
            )
        if "recipe_box_search" in url:
            return _mock_response(payload={"collectables": [], "collectables_count": 8})
        raise AssertionError(f"Unexpected URL: {url}")

    session.get.side_effect = fake_get
    prompts = iter(["1"])
    collection_id, label = prompt_collection_choice(
        client,
        prompt_fn=lambda _msg: next(prompts),
    )

    assert collection_id is None
    assert label == "All saved recipes"


def test_prompt_collection_choice_fallback_when_collections_unavailable(
    credentials: NytCredentials,
) -> None:
    from src.grocery_wizard.integrations.nyt_cooking import NytNetworkError

    client = NYTCookingClient(credentials, session=MagicMock())
    with (
        patch.object(
            client,
            "list_collections",
            side_effect=NytNetworkError("collections unavailable"),
        ),
        patch.object(
            client,
            "list_saved_recipes",
            return_value={"collectables": [], "collectables_count": 5},
        ),
    ):
        prompts = iter(["y"])
        collection_id, label = prompt_collection_choice(
            client,
            prompt_fn=lambda msg: next(prompts),
            on_info=lambda _msg: None,
        )

    assert collection_id is None
    assert label == "All saved recipes"


def test_prompt_collection_choice_cancelled(credentials: NytCredentials) -> None:
    client = NYTCookingClient(credentials, session=MagicMock())
    with patch.object(
        client,
        "list_collections",
        return_value=[NytCollection(id="1", name="Weeknight", recipe_count=2)],
    ), patch.object(
        client,
        "list_saved_recipes",
        return_value={"collectables": [], "collectables_count": 2},
    ):
        with pytest.raises(NytSyncCancelled):
            prompt_collection_choice(client, prompt_fn=lambda _msg: "")


def test_cmd_nyt_sync_interactive_picks_folder(capsys: pytest.CaptureFixture[str]) -> None:
    from src.grocery_wizard.cli.main import cmd_nyt_sync

    with (
        patch("src.grocery_wizard.cli.main.load_config"),
        patch("src.grocery_wizard.cli.main.NotionRecipesDB"),
        patch("src.grocery_wizard.integrations.nyt_cooking.NYTCookingClient"),
        patch(
            "src.grocery_wizard.integrations.nyt_cooking.prompt_collection_choice",
            return_value=("10", "Weeknight"),
        ) as prompt_mock,
        patch(
            "src.grocery_wizard.integrations.nyt_cooking.sync_saved_recipes_to_notion",
            return_value=MagicMock(
                total=2,
                skipped_existing=0,
                created=2,
                dry_run=0,
                failed=0,
            ),
        ) as sync_mock,
    ):
        code = cmd_nyt_sync(argparse_namespace(collection=None, dry_run=False, no_confirm=True))

    assert code == 0
    prompt_mock.assert_called_once()
    sync_mock.assert_called_once()
    kwargs = sync_mock.call_args.kwargs
    assert kwargs["collection_id"] == "10"
    assert kwargs["collection_label"] == "Weeknight"
    assert kwargs["collection_name"] is None


def test_cli_nyt_auth_status_not_configured(capsys: pytest.CaptureFixture[str]) -> None:
    from src.grocery_wizard.cli.main import cmd_nyt_auth_status

    with patch(
        "src.grocery_wizard.integrations.nyt_cooking.credentials_status",
        return_value={"configured": False, "regi_id": None},
    ):
        code = cmd_nyt_auth_status(argparse_namespace())

    assert code == 1
    assert "not configured" in capsys.readouterr().out


def argparse_namespace(**kwargs: object) -> MagicMock:
    ns = MagicMock()
    for key, value in kwargs.items():
        setattr(ns, key, value)
    return ns


def test_cli_nyt_saved_lists_recipes(capsys: pytest.CaptureFixture[str]) -> None:
    from src.grocery_wizard.cli.main import cmd_nyt_saved
    from src.grocery_wizard.integrations.nyt_cooking import NytSavedRecipe

    saved = [
        NytSavedRecipe(
            id="1",
            name="Pasta",
            url="https://cooking.nytimes.com/recipes/1-pasta",
            author="Chef",
        )
    ]
    with patch(
        "src.grocery_wizard.integrations.nyt_cooking.NYTCookingClient"
    ) as client_cls:
        client_cls.return_value.iter_all_saved_recipes.return_value = iter(saved)
        code = cmd_nyt_saved(argparse_namespace(collection=None))

    assert code == 0
    output = capsys.readouterr().out
    assert "Pasta" in output
    assert "Total: 1" in output
