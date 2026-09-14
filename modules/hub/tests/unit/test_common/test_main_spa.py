from pathlib import Path
from unittest.mock import patch

from app.main import _resolve_ui_dist, create_app
from starlette.testclient import TestClient


def test_resolve_ui_dist_none(tmp_path: Path):
    with patch.dict("os.environ", {"UI_DIST_PATH": str(tmp_path / "non_existent")}):
        assert _resolve_ui_dist() is None


def test_resolve_ui_dist_custom(tmp_path: Path):
    index_file = tmp_path / "index.html"
    index_file.write_text("<!DOCTYPE html><html><body>Test SPA</body></html>")

    with patch.dict("os.environ", {"UI_DIST_PATH": str(tmp_path)}):
        resolved = _resolve_ui_dist()
        assert resolved == tmp_path


def test_root_redirect_when_no_ui(tmp_path: Path):
    with patch.dict("os.environ", {"UI_DIST_PATH": str(tmp_path / "non_existent")}):
        app = create_app()
        client = TestClient(app)
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/docs"


def test_spa_served_when_ui_present(tmp_path: Path):
    index_file = tmp_path / "index.html"
    index_file.write_text("<!DOCTYPE html><html><body>Test SPA</body></html>")
    app_dir = tmp_path / "_app"
    app_dir.mkdir()
    asset_file = app_dir / "style.css"
    asset_file.write_text("body { color: red; }")

    with patch.dict("os.environ", {"UI_DIST_PATH": str(tmp_path)}):
        app = create_app()
        client = TestClient(app)

        # Root returns index.html
        root_res = client.get("/")
        assert root_res.status_code == 200
        assert "Test SPA" in root_res.text

        # Client-side route fallback returns index.html
        route_res = client.get("/projects/runs")
        assert route_res.status_code == 200
        assert "Test SPA" in route_res.text

        # Static asset returns asset content
        asset_res = client.get("/_app/style.css")
        assert asset_res.status_code == 200
        assert "color: red" in asset_res.text
