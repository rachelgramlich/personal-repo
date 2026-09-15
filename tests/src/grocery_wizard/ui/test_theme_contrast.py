"""Theme token contrast for the Streamlit UI."""

from __future__ import annotations

import pytest

from src.grocery_wizard.ui.theme import (
    GW_THEME,
    MIN_CONTRAST_RATIO_AA,
    assert_theme_contrast_aa,
    contrast_ratio,
    theme_contrast_pairs,
)


def test_gw_theme_pairs_meet_wcag_aa() -> None:
    assert_theme_contrast_aa(GW_THEME, minimum=MIN_CONTRAST_RATIO_AA)


@pytest.mark.parametrize(("label", "foreground", "background"), theme_contrast_pairs())
def test_individual_pairs(label: str, foreground: str, background: str) -> None:
    ratio = contrast_ratio(foreground, background)
    assert ratio >= MIN_CONTRAST_RATIO_AA, f"{label}: {ratio:.2f} for {foreground} on {background}"
