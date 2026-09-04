"""Shared fixtures for ingredient normalization and sync tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def _ensure_nltk() -> None:
    try:
        import nltk

        nltk.data.find("taggers/averaged_perceptron_tagger_eng")
    except LookupError:
        import nltk

        nltk.download("averaged_perceptron_tagger_eng", quiet=True)


_ensure_nltk()

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"
_NOTION_FIXTURE_PATH = _FIXTURES_DIR / "notion_ingredient_cases.json"
_PIPELINE_FIXTURE_PATH = _FIXTURES_DIR / "ingredient_pipeline_cases.json"


def load_notion_ingredient_cases() -> list[dict[str, Any]]:
    return json.loads(_NOTION_FIXTURE_PATH.read_text(encoding="utf-8"))


def load_pipeline_cases() -> list[dict[str, Any]]:
    return json.loads(_PIPELINE_FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def notion_ingredient_cases() -> list[dict[str, Any]]:
    return load_notion_ingredient_cases()


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "notion_case" in metafunc.fixturenames:
        cases = load_notion_ingredient_cases()
        ids = [f"{case['recipe']}|{case['raw_line'][:40].replace(chr(10), ' ')}" for case in cases]
        metafunc.parametrize("notion_case", cases, ids=ids)

    if "single_line_pipeline_case" in metafunc.fixturenames:
        cases = [
            case
            for case in load_pipeline_cases()
            if not case.get("aggregate") and "raw_line" in case
        ]
        ids = [case["label"] for case in cases]
        metafunc.parametrize("single_line_pipeline_case", cases, ids=ids)

    if "aggregate_pipeline_case" in metafunc.fixturenames:
        cases = [case for case in load_pipeline_cases() if case.get("aggregate")]
        ids = [case["label"] for case in cases]
        metafunc.parametrize("aggregate_pipeline_case", cases, ids=ids)


@pytest.fixture(scope="session")
def pipeline_cases() -> list[dict[str, Any]]:
    return load_pipeline_cases()
