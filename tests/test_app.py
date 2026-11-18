from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).parent.parent / "app" / "streamlit_app.py"


def test_app_runs_and_shows_the_smile_and_rejections():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    assert len(at.get("plotly_chart")) >= 1
    assert len(at.dataframe) == 1  # rejected quotes by reason
