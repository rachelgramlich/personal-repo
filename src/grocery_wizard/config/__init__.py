"""Environment configuration for Grocery Wizard."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _PACKAGE_DIR.parent.parent

# Committed package configuration (pantry staples, etc.).
CONFIG_DIR = Path(__file__).resolve().parent
PANTRY_PATH = CONFIG_DIR / "pantry.txt"
STORE_AISLES_PATH = CONFIG_DIR / "store_aisles.txt"
RECURRING_WEEKLY_ITEMS_PATH = CONFIG_DIR / "recurring_weekly_items.txt"

# Per-week local runtime data (gitignored via .local/).
DATA_DIR = Path(".local/grocery_wizard")
LEGACY_DATA_DIR = Path(".grocery_wizard")

WEEK_PLAN_PATH = DATA_DIR / "week_plan.json"
LEGACY_WEEK_PLAN_PATH = LEGACY_DATA_DIR / "week_plan.json"
FEEDBACK_PATH = DATA_DIR / "feedback.json"
NYT_LAST_SYNC_PATH = DATA_DIR / "nyt_last_sync.json"


class Config(BaseSettings):
    """Notion and Grocery Wizard settings loaded from environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    notion_api_key: str = Field(validation_alias="NOTION_API_KEY")
    notion_database_id: str = Field(validation_alias="NOTION_DATABASE_ID")
    default_meals: int = Field(default=7, validation_alias="GROCERY_WIZARD_DEFAULT_MEALS")
    notion_data_source_id: str | None = Field(
        default=None,
        validation_alias="NOTION_DATA_SOURCE_ID",
    )
    name_column: str | None = Field(default=None, validation_alias="GROCERY_WIZARD_NAME_COLUMN")
    link_column: str | None = Field(default=None, validation_alias="GROCERY_WIZARD_LINK_COLUMN")
    ingredients_column: str | None = Field(
        default=None,
        validation_alias="GROCERY_WIZARD_INGREDIENTS_COLUMN",
    )
    nyt_synced_column: str | None = Field(
        default=None,
        validation_alias="GROCERY_WIZARD_NYT_SYNCED_COLUMN",
    )

    @field_validator(
        "notion_api_key",
        "notion_database_id",
        "notion_data_source_id",
        "name_column",
        "link_column",
        "ingredients_column",
        "nyt_synced_column",
        mode="before",
    )
    @classmethod
    def _strip_string(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("notion_api_key")
    @classmethod
    def _require_api_key(cls, value: str | None) -> str:
        if not value:
            raise ValueError("NOTION_API_KEY is required (set in .env or Cloud Agent Secrets)")
        return value

    @field_validator("notion_database_id")
    @classmethod
    def _require_database_id(cls, value: str | None) -> str:
        if not value:
            raise ValueError("NOTION_DATABASE_ID is required (set in .env or Cloud Agent Secrets)")
        return value


def load_config() -> Config:
    """Load configuration from environment variables and ``.env``."""
    try:
        return Config()
    except ValidationError as exc:
        for error in exc.errors():
            loc = error.get("loc", ())
            if "notion_api_key" in loc:
                raise ValueError(
                    "NOTION_API_KEY is required (set in .env or Cloud Agent Secrets)"
                ) from exc
            if "notion_database_id" in loc:
                raise ValueError(
                    "NOTION_DATABASE_ID is required (set in .env or Cloud Agent Secrets)"
                ) from exc
        raise
