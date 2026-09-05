"""Regression tests for grocery list display in the Streamlit UI."""

from __future__ import annotations

from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[4] / "src" / "grocery_wizard" / "ui" / "app.py"


def test_grocery_final_list_syncs_session_state_before_keyed_text_area() -> None:
    """Keyed text_area ignores value= on reruns; app must push fresh list_text into session state."""
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'st.session_state["grocery_final_list"] = list_text' in source
    assert 'key="grocery_final_list"' in source
    assert "value=list_text" not in source


def test_keyed_text_area_with_session_state_sync_updates_on_rerun(tmp_path: Path) -> None:
    """Session-state sync before keyed text_area refreshes display on reruns."""
    from streamlit.testing.v1 import AppTest

    test_app = """
import streamlit as st

if "counter" not in st.session_state:
    st.session_state.counter = 0

if st.button("increment"):
    st.session_state.counter += 1

computed = f"Value: {st.session_state.counter}"
st.session_state["display_key"] = computed
st.text_area("display", key="display_key")
"""
    app_file = tmp_path / "streamlit_sync_widget_fixture.py"
    app_file.write_text(test_app, encoding="utf-8")

    at = AppTest.from_file(str(app_file), default_timeout=30)
    at.run()
    at.button[0].click().run()

    assert at.text_area[0].value == "Value: 1"
