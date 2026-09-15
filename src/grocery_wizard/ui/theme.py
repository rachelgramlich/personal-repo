"""Grocery Wizard Streamlit theme tokens, contrast checks, and injected CSS.

CSS targets Streamlit widget roots (``stTextInput``, ``stMultiSelect``, etc.) and
shared Base Web nodes (``data-baseweb="input"``, ``select``, ``tag``) so new widgets
pick up the same tokens when they reuse those primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# WCAG 2.x contrast ratio for normal text (AA).
MIN_CONTRAST_RATIO_AA: Final[float] = 4.5


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    bg: str
    text: str
    text_muted: str
    input_bg: str
    accent: str
    blue: str
    blue_strong: str
    blue_text: str
    on_accent: str = "#ffffff"


GW_THEME = ThemeTokens(
    bg="#ffe4f0",
    text="#5c1040",
    text_muted="#7a2858",
    input_bg="#fff9fc",
    accent="#8b1a5c",
    blue="#b8d9f0",
    blue_strong="#6baee0",
    blue_text="#1a4a6e",
)


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        msg = f"Expected #RRGGBB, got {hex_color!r}"
        raise ValueError(msg)
    r = int(value[0:2], 16) / 255.0
    g = int(value[2:4], 16) / 255.0
    b = int(value[4:6], 16) / 255.0
    return r, g, b


def _relative_luminance(hex_color: str) -> float:
    r, g, b = _hex_to_rgb(hex_color)

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(foreground: str, background: str) -> float:
    """Return WCAG contrast ratio between two #RRGGBB colors."""
    l1 = _relative_luminance(foreground)
    l2 = _relative_luminance(background)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def theme_contrast_pairs(tokens: ThemeTokens = GW_THEME) -> list[tuple[str, str, str]]:
    """Foreground/background pairs that must stay readable in the UI."""
    return [
        ("body text on page", tokens.text, tokens.bg),
        ("body text on inputs", tokens.text, tokens.input_bg),
        ("muted text on page", tokens.text_muted, tokens.bg),
        ("tag text on tag fill", tokens.blue_text, tokens.blue),
        ("primary button label", tokens.on_accent, tokens.accent),
    ]


def assert_theme_contrast_aa(
    tokens: ThemeTokens = GW_THEME,
    *,
    minimum: float = MIN_CONTRAST_RATIO_AA,
) -> None:
    for label, fg, bg in theme_contrast_pairs(tokens):
        ratio = contrast_ratio(fg, bg)
        if ratio < minimum:
            msg = f"{label}: contrast {ratio:.2f} < {minimum} ({fg} on {bg})"
            raise AssertionError(msg)


def app_theme_css(tokens: ThemeTokens = GW_THEME) -> str:
    """Return the ``<style>`` block for ``st.markdown(..., unsafe_allow_html=True)``."""
    t = tokens
    border = "#d48aad"
    return f"""
        <style>
        /*
         * Covered Streamlit surfaces: text inputs/areas, number inputs, selectbox,
         * multiselect (tags + value field), disabled fields, code/pre blocks, tabs,
         * expanders, secondary buttons, checkboxes, radios, and select dropdown rows.
         * Shared hooks: [data-baseweb="input"|"select"|"tag"] and widget class roots.
         */
        :root {{
            --gw-bg: {t.bg};
            --gw-text: {t.text};
            --gw-text-muted: {t.text_muted};
            --gw-input-bg: {t.input_bg};
            --gw-accent: {t.accent};
            --gw-blue: {t.blue};
            --gw-blue-strong: {t.blue_strong};
            --gw-blue-text: {t.blue_text};
        }}

        html {{
            color-scheme: light;
        }}

        .stApp {{
            background-color: var(--gw-bg);
            color: var(--gw-text);
            color-scheme: light;
        }}

        .stApp h1, .stApp h2, .stApp h3, .stApp h4,
        .stApp label, .stApp p, .stApp li,
        .stApp [data-testid="stMarkdownContainer"],
        .stApp [data-testid="stWidgetLabel"] p,
        .stApp [data-testid="stCaptionContainer"] {{
            color: var(--gw-text);
        }}

        /* Avoid painting all spans (breaks primary buttons and tag chips). */
        .stApp span:not(.stButton span):not([data-baseweb="tag"] span) {{
            color: inherit;
        }}

        .stApp .stCaption, .stApp small {{
            color: var(--gw-text-muted);
        }}

        /* Streamlit 1.6x widget shells (textarea/input use transparent inner + colored root) */
        [data-testid="stTextInputRootElement"],
        [data-testid="stTextAreaRootElement"],
        [data-testid="stNumberInputContainer"],
        [data-testid="stMultiSelectTagsContainer"],
        /* React Aria select/multiselect closed triggers (emotion styled, not baseweb) */
        [data-testid="stMultiSelect"] div:has([data-testid="stMultiSelectTagsContainer"]),
        [data-testid="stSelectbox"] div:has(button[aria-label="Open"]),
        [data-testid="stSelectbox"] div:has(> input:not([type="hidden"])),
        .stSelectbox div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] > div {{
            background-color: var(--gw-input-bg) !important;
            border-color: {border} !important;
            color: var(--gw-text) !important;
        }}

        [data-testid="stMultiSelect"] input,
        [data-testid="stSelectbox"] input,
        [data-testid="stNumberInputField"] {{
            background-color: transparent !important;
            color: var(--gw-text) !important;
            -webkit-text-fill-color: var(--gw-text) !important;
        }}

        [data-testid="stMultiSelect"] input::placeholder,
        [data-testid="stSelectbox"] input::placeholder,
        [data-testid="stNumberInputField"]::placeholder,
        [data-testid="stTextInputField"]::placeholder,
        [data-testid="stTextAreaRootElement"] textarea::placeholder,
        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder {{
            color: var(--gw-text-muted) !important;
            -webkit-text-fill-color: var(--gw-text-muted) !important;
            opacity: 0.72 !important;
            font-style: italic;
        }}

        [data-testid="stNumberInputStepDown"],
        [data-testid="stNumberInputStepUp"] {{
            background-color: var(--gw-input-bg) !important;
            color: var(--gw-text) !important;
            border-color: {border} !important;
        }}

        [data-testid="stNumberInputStepDown"]:hover:enabled,
        [data-testid="stNumberInputStepUp"]:hover:enabled {{
            background-color: var(--gw-accent) !important;
            color: {t.on_accent} !important;
        }}

        /* Text fields — native controls and Base Web wrappers */
        .stTextInput input,
        .stTextArea textarea,
        .stNumberInput input,
        .stDateInput input,
        [data-testid="stTextInputField"],
        [data-baseweb="input"] input,
        [data-baseweb="select"] input,
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        div[data-baseweb="base-input"],
        div[data-baseweb="base-input"] > div {{
            background-color: var(--gw-input-bg) !important;
            color: var(--gw-text) !important;
            border-color: {border} !important;
            -webkit-text-fill-color: var(--gw-text) !important;
        }}

        [data-testid="stTextInputField"],
        [data-testid="stTextAreaRootElement"] textarea {{
            background-color: transparent !important;
        }}

        [data-testid="stSelectbox"] input:not([type="hidden"]) {{
            color: var(--gw-text) !important;
            -webkit-text-fill-color: var(--gw-text) !important;
        }}

        .stTextInput input:disabled,
        .stTextArea textarea:disabled,
        .stNumberInput input:disabled,
        [data-baseweb="input"] input:disabled {{
            background-color: var(--gw-input-bg) !important;
            color: var(--gw-text) !important;
            -webkit-text-fill-color: var(--gw-text) !important;
            opacity: 1 !important;
        }}

        [data-baseweb="input"] span,
        [data-baseweb="select"] span,
        [data-baseweb="select"] div[value] {{
            color: var(--gw-text) !important;
        }}

        [data-testid="stText"] pre,
        [data-testid="stText"] code {{
            background-color: var(--gw-input-bg) !important;
            color: var(--gw-text) !important;
        }}

        [data-baseweb="tab"] {{
            color: var(--gw-text-muted) !important;
        }}

        [data-baseweb="tab"][aria-selected="true"] {{
            color: var(--gw-text) !important;
            border-bottom-color: var(--gw-accent) !important;
        }}

        .stButton button[kind="primary"],
        .stButton button[data-testid="stBaseButton-primary"],
        .stButton button[data-testid="baseButton-primary"],
        .stDownloadButton button[data-testid="stBaseButton-primary"],
        .stDownloadButton button {{
            background-color: var(--gw-accent) !important;
            border-color: var(--gw-accent) !important;
            color: {t.on_accent} !important;
            font-weight: 600 !important;
        }}

        .stButton button[kind="primary"] *,
        .stButton button[data-testid="stBaseButton-primary"] *,
        .stButton button[data-testid="baseButton-primary"] *,
        .stDownloadButton button[data-testid="stBaseButton-primary"] *,
        .stDownloadButton button * {{
            color: {t.on_accent} !important;
            -webkit-text-fill-color: {t.on_accent} !important;
            font-weight: 600 !important;
        }}

        .stButton button[kind="secondary"],
        .stButton button[data-testid="baseButton-secondary"] {{
            background-color: var(--gw-input-bg) !important;
            border-color: {border} !important;
            color: var(--gw-text) !important;
        }}

        .stButton button[kind="secondary"] p,
        .stButton button[kind="secondary"] span,
        .stButton button[data-testid="baseButton-secondary"] p,
        .stButton button[data-testid="baseButton-secondary"] span {{
            color: var(--gw-text) !important;
        }}

        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] details > summary {{
            background-color: var(--gw-input-bg) !important;
            color: var(--gw-text) !important;
            border: 1px solid {border} !important;
            border-radius: 0.25rem !important;
        }}

        [data-testid="stExpander"] summary:hover,
        [data-testid="stExpander"] summary:focus-visible,
        [data-testid="stExpander"] details[open] > summary {{
            background-color: var(--gw-input-bg) !important;
            color: var(--gw-text) !important;
        }}

        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
        [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p {{
            color: var(--gw-text) !important;
        }}

        [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
            border: 1px solid {border} !important;
            border-top: none !important;
            background-color: var(--gw-bg) !important;
        }}

        .stCheckbox label[data-baseweb="checkbox"] > span[data-checked="true"],
        label[data-baseweb="checkbox"] > span[aria-checked="true"] {{
            background-color: var(--gw-blue-strong) !important;
            border-color: var(--gw-blue-strong) !important;
        }}

        .stCheckbox label[data-baseweb="checkbox"] > span[data-checked="false"],
        label[data-baseweb="checkbox"] > span[aria-checked="false"] {{
            border-color: var(--gw-blue-strong) !important;
        }}

        .stRadio label[data-baseweb="radio"] > div:first-child {{
            border-color: var(--gw-blue-strong) !important;
        }}

        .stRadio label[data-baseweb="radio"] > div:first-child[aria-checked="true"],
        label[data-baseweb="radio"] div[data-checked="true"] {{
            background-color: var(--gw-blue-strong) !important;
            border-color: var(--gw-blue-strong) !important;
        }}

        [data-baseweb="tag"] {{
            background-color: var(--gw-blue) !important;
            color: var(--gw-blue-text) !important;
            border-color: var(--gw-blue-strong) !important;
        }}

        [data-baseweb="tag"] svg {{
            fill: var(--gw-blue-text) !important;
        }}

        li[role="option"][aria-selected="true"] {{
            background-color: var(--gw-blue) !important;
            color: var(--gw-blue-text) !important;
        }}

        li[role="option"] {{
            color: var(--gw-text) !important;
            background-color: var(--gw-input-bg) !important;
        }}

        li[role="option"]:hover,
        li[role="option"][data-highlighted="true"] {{
            background-color: var(--gw-blue) !important;
            color: var(--gw-blue-text) !important;
        }}

        /* Portaled select/multiselect menus (outside .stApp) */
        [data-testid="stSelectboxVirtualDropdown"],
        [data-testid="stMultiSelectDropdown"] {{
            background-color: var(--gw-input-bg) !important;
            color: var(--gw-text) !important;
            border: 1px solid {border} !important;
            color-scheme: light;
        }}

        [data-testid="stSelectboxVirtualDropdown"] *,
        [data-testid="stMultiSelectDropdown"] * {{
            color: var(--gw-text);
        }}

        [data-testid="stSelectboxVirtualDropdown"] [role="listbox"],
        [data-testid="stMultiSelectDropdown"] [role="listbox"] {{
            background-color: var(--gw-input-bg) !important;
        }}

        .gw-pantry-aisle-heading {{
            color: var(--gw-text);
            font-size: 1.02rem;
            font-weight: 700;
            margin: 0.65rem 0 0.12rem 0;
            padding-bottom: 0.1rem;
            border-bottom: 1px solid {border};
        }}

        .gw-pantry-aisle-heading:first-of-type {{
            margin-top: 0.2rem;
        }}

        p.gw-pantry-item,
        p.gw-recurring-item {{
            color: var(--gw-text);
            font-size: 0.92rem;
            line-height: 1.15;
            margin: 0 0 0 0.75rem;
            padding: 0;
        }}

        [data-testid="stHorizontalBlock"]:has(p.gw-pantry-item),
        [data-testid="stHorizontalBlock"]:has(p.gw-recurring-item) {{
            align-items: center !important;
            gap: 0.2rem !important;
            margin-bottom: 0 !important;
        }}

        [data-testid="stHorizontalBlock"]:has(p.gw-pantry-item) [data-testid="stColumn"],
        [data-testid="stHorizontalBlock"]:has(p.gw-recurring-item) [data-testid="stColumn"] {{
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            min-height: 0 !important;
        }}

        [data-testid="stHorizontalBlock"]:has(p.gw-pantry-item) .stButton,
        [data-testid="stHorizontalBlock"]:has(p.gw-recurring-item) .stButton {{
            margin: 0 !important;
        }}

        [data-testid="stHorizontalBlock"]:has(p.gw-pantry-item) .stButton button,
        [data-testid="stHorizontalBlock"]:has(p.gw-recurring-item) .stButton button {{
            padding: 0 0.35rem !important;
            min-height: 1.25rem !important;
            height: 1.25rem !important;
            min-width: 1.25rem !important;
            width: 1.25rem !important;
            font-size: 0.95rem !important;
            line-height: 1 !important;
        }}

        [data-testid="stHorizontalBlock"]:has(p.gw-pantry-item) .stButton button p,
        [data-testid="stHorizontalBlock"]:has(p.gw-recurring-item) .stButton button p {{
            font-size: 0.95rem !important;
            line-height: 1 !important;
        }}

        [data-testid="stToolbar"], footer, #MainMenu {{
            visibility: hidden;
        }}
        [data-testid="stToolbar"] {{
            height: 0;
        }}
        </style>
        """
