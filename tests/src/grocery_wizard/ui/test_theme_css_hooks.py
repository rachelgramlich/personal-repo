"""Regression hooks for Streamlit 1.6x widget CSS (issue #120)."""

from __future__ import annotations

from src.grocery_wizard.ui.theme import app_theme_css

# Selectors that must stay in app_theme_css for reported black-box scenarios.
_REQUIRED_CSS_FRAGMENTS = (
    "stTextInputRootElement",
    "stTextAreaRootElement",
    'stTextAreaRootElement"] textarea::placeholder',
    "stMultiSelectTagsContainer",
    '[data-testid="stMultiSelectTagsContainer"] [data-tag]',
    'div:has(button[aria-label="Open"])',
    "stNumberInputContainer",
    "stNumberInputStepDown",
    "stBaseButton-primary",
    '[data-testid="stExpander"] summary',
    "stSelectboxVirtualDropdown",
    "stMultiSelectDropdown",
    "color-scheme: light",
)


def test_app_theme_css_covers_streamlit_16_widget_hooks() -> None:
    css = app_theme_css()
    missing = [frag for frag in _REQUIRED_CSS_FRAGMENTS if frag not in css]
    assert not missing, f"app_theme_css missing hooks: {missing}"
