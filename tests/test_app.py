from pathlib import Path

import conftest
import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parent.parent / "app" / "streamlit_app.py"
REAL_SNAPSHOT = conftest.REAL_SNAPSHOT.name


@pytest.fixture
def app(monkeypatch) -> AppTest:
    monkeypatch.setenv("IVSURFACE_SNAPSHOT_DIR", str(conftest.FIXTURES))
    return AppTest.from_file(str(APP), default_timeout=30)


def assert_all_views_render(at: AppTest) -> None:
    assert not at.exception
    assert len(at.get("plotly_chart")) == 4  # smiles, 3D surface, ATM term structure, Durrleman g
    assert [m.label for m in at.metric] == [
        "Interpolated: butterfly",
        "Interpolated: calendar",
        "SVI: butterfly",
        "SVI: calendar",
    ]
    assert len(at.dataframe) == 3  # SVI parameters, worst violations, rejected quotes by reason


def test_app_runs_on_the_synthetic_surface_by_default(app):
    at = app.run()
    assert at.selectbox(key="source").value == "Synthetic surface"
    assert_all_views_render(at)


def test_app_runs_on_a_saved_deribit_snapshot(app):
    at = app.run()
    assert REAL_SNAPSHOT in at.selectbox(key="source").options
    at = at.selectbox(key="source").select(REAL_SNAPSHOT).run()
    assert_all_views_render(at)
    assert any("mark" in c.value for c in at.caption)  # explains mid IV vs Deribit's mark IV


def test_the_arbitrage_tab_can_inspect_either_surface(app):
    at = app.run()
    assert at.radio(key="inspect").options == ["SVI", "Interpolated"]
    at = at.radio(key="inspect").set_value("Interpolated").run()
    assert not at.exception


def test_app_falls_back_to_the_interpolated_surface_when_svi_cannot_fit(app, monkeypatch):
    # Thin expiries (fewer than five usable quotes) cannot be SVI-fitted; force that everywhere.
    import streamlit as st

    from ivsurface import pipeline

    monkeypatch.setattr(pipeline, "SVI_MIN_QUOTES", 10_000)
    st.cache_resource.clear()
    at = app.run()
    st.cache_resource.clear()
    assert not at.exception
    assert len(at.get("plotly_chart")) == 4
    assert [m.label for m in at.metric] == ["Interpolated: butterfly", "Interpolated: calendar"]
    assert at.radio(key="inspect").options == ["Interpolated"]
