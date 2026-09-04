"""Shared fixtures for ingredient normalization and sync tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "notion_ingredient_cases.json"


def load_notion_ingredient_cases() -> list[dict[str, Any]]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def notion_ingredient_cases() -> list[dict[str, Any]]:
    return load_notion_ingredient_cases()


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "notion_case" in metafunc.fixturenames:
        cases = load_notion_ingredient_cases()
        ids = [f"{case['recipe']}|{case['raw_line'][:40].replace(chr(10), ' ')}" for case in cases]
        metafunc.parametrize("notion_case", cases, ids=ids)
