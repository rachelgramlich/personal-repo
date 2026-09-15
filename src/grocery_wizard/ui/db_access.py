"""Shared Notion DB handle for Streamlit reruns."""

from __future__ import annotations

import streamlit as st

from src.grocery_wizard.config import load_config
from src.grocery_wizard.integrations.notion import NotionRecipesDB


@st.cache_resource
def get_db() -> NotionRecipesDB:
    config = load_config()
    return NotionRecipesDB(config)
