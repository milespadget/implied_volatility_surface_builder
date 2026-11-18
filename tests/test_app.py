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
    assert [m.label for m in at.metric] == ["Butterfly violations", "Calendar violations"]
    assert len(at.dataframe) == 2  # worst arbitrage violations, rejected quotes by reason


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
