from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_project_status() -> None:
    app = AppTest.from_file(Path(__file__).parents[2] / "app.py").run()

    assert not app.exception
    assert app.title[0].value == "AIOps Log Anomaly Detection"
    assert "not implemented yet" in app.info[0].value
