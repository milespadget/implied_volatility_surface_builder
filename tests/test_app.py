import json
from pathlib import Path

import conftest
import pytest
from streamlit.proto.Metric_pb2 import Metric as MetricProto
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


# Presentation (ticket 08). Charts in page order: smiles, 3D surface, ATM term structure, Durrleman g.


def chart(at: AppTest, index: int) -> dict:
    return json.loads(at.get("plotly_chart")[index].proto.spec)


def luminance(rgb: str) -> float:
    r, g, b = (float(c) for c in rgb.removeprefix("rgb(").removesuffix(")").split(","))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_each_expiry_has_its_own_colour_light_for_short_dark_for_long(app):
    smiles = chart(app.run(), 0)["data"]
    markers = [t for t in smiles if t.get("showlegend", True)]  # the legend: one filled-marker trace per expiry
    colours = [t["marker"]["color"] for t in markers]
    assert len(markers) == 8 and len(set(colours)) == 8
    lightness = [luminance(c) for c in colours]
    assert lightness == sorted(lightness, reverse=True)
    for t in smiles:  # fitted curves share their expiry's colour
        if t["mode"] == "lines":
            expiry = t["name"].split()[0]
            assert t["line"]["color"] == colours[[m["name"] for m in markers].index(expiry)]


def test_the_3d_surface_shows_percent_titled_axes_and_a_set_camera(app):
    spec = chart(app.run(), 1)
    assert spec["data"][0]["colorbar"]["tickformat"] == ".0%"
    scene = spec["layout"]["scene"]
    assert scene["zaxis"]["tickformat"] == ".0%"
    assert all(scene[axis]["title"]["text"] for axis in ("xaxis", "yaxis", "zaxis"))
    assert "eye" in scene["camera"]


def test_term_structure_legend_entries_are_capitalised(app):
    names = [t["name"] for t in chart(app.run(), 2)["data"]]
    assert "True" in names
    assert all(n[0].isupper() for n in names)


def test_arbitrage_metrics_show_the_share_without_an_arrow(app):
    for metric in app.run().metric:
        assert "of points checked" in metric.proto.delta
        assert metric.proto.direction == MetricProto.MetricDirection.NONE


def test_open_markers_are_the_true_iv_on_synthetic_data_and_mark_iv_on_deribit_data(app):
    at = app.run()
    assert not any("Deribit" in c.value for c in at.caption)
    assert any("true IV" in c.value for c in at.caption)
    assert any(t["name"].endswith("true IV") for t in chart(at, 0)["data"])
    at = at.selectbox(key="source").select(REAL_SNAPSHOT).run()
    assert any("Deribit's mark IV" in c.value for c in at.caption)
    assert any(t["name"].endswith("Deribit mark IV") for t in chart(at, 0)["data"])
