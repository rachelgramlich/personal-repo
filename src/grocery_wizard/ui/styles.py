"""Inject Grocery Wizard theme CSS once per process."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.grocery_wizard.ui.theme import app_theme_css

_STATIC_CSS = Path(__file__).resolve().parent / "static" / "app_theme.css"


@st.cache_resource
def _cached_theme_markup() -> str:
    """Load static CSS when present; fall back to tokenized theme helper."""
    if _STATIC_CSS.is_file():
        css = _STATIC_CSS.read_text(encoding="utf-8")
        return f"<style>\n{css}\n</style>"
    return app_theme_css()


def inject_app_styles() -> None:
    st.markdown(_cached_theme_markup(), unsafe_allow_html=True)
