"""Environment configuration for Grocery Wizard."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_PACKAGE_DIR = Path(__file__).resolve().parent.parent

# Committed package configuration (pantry staples, etc.).
CONFIG_DIR = Path(__file__).resolve().parent
PANTRY_PATH = CONFIG_DIR / "pantry.txt"

# Per-week local runtime data (gitignored via .local/).
DATA_DIR = Path(".local/grocery_wizard")
LEGACY_DATA_DIR = Path(".grocery_wizard")

WEEK_PLAN_PATH = DATA_DIR / "week_plan.json"
LEGACY_WEEK_PLAN_PATH = LEGACY_DATA_DIR / "week_plan.json"
FEEDBACK_PATH = DATA_DIR / "feedback.json"
NYT_CREDENTIALS_PATH = DATA_DIR / "nyt_credentials.json"

load_dotenv()


@dataclass(frozen=True)
class Config:
    notion_api_key: str
    notion_database_id: str
    default_meals: int = 7
    notion_data_source_id: str | None = None
    name_column: str | None = None
    link_column: str | None = None
    ingredients_column: str | None = None


def load_config() -> Config:
    api_key = os.getenv("NOTION_API_KEY", "").strip()
    database_id = os.getenv("NOTION_DATABASE_ID", "").strip()
    if not api_key:
        raise ValueError("NOTION_API_KEY is required (set in .env)")
    if not database_id:
        raise ValueError("NOTION_DATABASE_ID is required (set in .env)")

    default_meals = int(os.getenv("GROCERY_WIZARD_DEFAULT_MEALS", "7"))

    return Config(
        notion_api_key=api_key,
        notion_database_id=database_id,
        default_meals=default_meals,
        notion_data_source_id=_optional_env("NOTION_DATA_SOURCE_ID"),
        name_column=_optional_env("GROCERY_WIZARD_NAME_COLUMN"),
        link_column=_optional_env("GROCERY_WIZARD_LINK_COLUMN"),
        ingredients_column=_optional_env("GROCERY_WIZARD_INGREDIENTS_COLUMN"),
    )


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None
