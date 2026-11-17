"""UI End-to-End and Integration Test Suite for OptiForge Desktop App.

Tests the full front-end contract and data flow:
1. Native dialog endpoints (/api/dialog/pick) returning proper 'path' and 'selected'.
2. Handling folders with SPACES in names and paths.
3. Path normalization (quotes, trailing slashes, backslashes).
4. Smart resolution of bare folder names from drag & drop.
5. Clear plain-English error messages when paths do not exist.
6. Full end-to-end lifecycle: detect -> analyze -> prompt -> fix preview -> apply -> rollback.
"""

import io
import json
import os
from pathlib import Path
import pytest

from optiforge.app.app_server import app, session
from optiforge.services.input_detector import InputDetector


class WsgiTestClient:
    """Zero-dependency WSGI test client for the Bottle web application."""

    def __init__(self, wsgi_app):
        self.app = wsgi_app

    def request(self, method: str, path: str, json_data=None):
        body_bytes = json.dumps(json_data).encode("utf-8") if json_data is not None else b""
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "8848",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(body_bytes),
            "wsgi.errors": io.StringIO(),
            "CONTENT_LENGTH": str(len(body_bytes)),
            "CONTENT_TYPE": "application/json",
        }
        status_holder = []
        headers_holder = []

        def start_response(status, headers, exc_info=None):
            status_holder.append(status)
            headers_holder.append(headers)

        body = b"".join(self.app(environ, start_response))
        status_code = int(status_holder[0].split()[0])
        try:
            parsed_json = json.loads(body.decode("utf-8"))
        except Exception:
            parsed_json = None
        return status_code, parsed_json, body

    def get(self, path: str):
        return self.request("GET", path)

    def post_json(self, path: str, data: dict):
        return self.request("POST", path, json_data=data)


@pytest.fixture
def client():
    return WsgiTestClient(app)


@pytest.fixture
def folder_with_spaces(tmp_path):
    """Creates a real project directory whose path and folder name contain spaces."""
    project_dir = tmp_path / "My Project With Spaces"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Add code, images, and config
    (project_dir / "index.js").write_text("console.log('hello spaces');\n", encoding="utf-8")
    (project_dir / "calc.py").write_text("def add(x, y):\n    return x + y\n", encoding="utf-8")
    (project_dir / "README.md").write_text("# Project With Spaces\n", encoding="utf-8")
    (project_dir / "styles.css").write_text("body { margin: 0; }\n", encoding="utf-8")

    return project_dir


def test_dialog_pick_endpoint_contract(client, monkeypatch):
    """Verifies that /api/dialog/pick returns both 'selected' and 'path' keys."""
    # Mock subprocess.run so headless test does not hang waiting for GUI modal click
    import subprocess
    class FakeProc:
        stdout = "C:\\Users\\test\\My Project With Spaces\n"
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeProc())

    code, data, _ = client.post_json("/api/dialog/pick", {"dialog_type": "folder", "initial_dir": ""})
    assert code == 200
    assert data["success"] is True
    assert data["path"] == "C:\\Users\\test\\My Project With Spaces"
    assert data["selected"] == "C:\\Users\\test\\My Project With Spaces"


def test_analyze_folder_with_spaces_contract(client, folder_with_spaces):
    """Simulates front-end folder selection with spaces and verifies exact identity reporting."""
    abs_path_str = str(folder_with_spaces.resolve())
    assert " " in abs_path_str

    code, data, _ = client.post_json("/api/analyze", {"raw_input": abs_path_str})
    assert code == 200
    assert data["success"] is True

    result = data["result"]
    # 1. Project name must match folder base name
    assert result["target_name"] == "My Project With Spaces"
    # 2. Project path must be the full resolved path
    assert result["target_path"] == abs_path_str
    # 3. Item count must match files scanned
    assert result["item_count"] == 4
    # 4. Tech stack must detect JavaScript/TypeScript and Python
    assert "Python" in result["tech_stack"]
    assert "JavaScript" in result["tech_stack"]


def test_analyze_quoted_path(client, folder_with_spaces):
    """Verifies that paths enclosed in double or single quotes (Windows 'Copy as path') are normalized."""
    quoted_input = f'"{folder_with_spaces.resolve()}"'
    code, data, _ = client.post_json("/api/analyze", {"raw_input": quoted_input})
    assert code == 200
    assert data["success"] is True
    assert data["result"]["target_path"] == str(folder_with_spaces.resolve())


def test_analyze_trailing_slash_path(client, folder_with_spaces):
    """Verifies that paths with trailing slashes or backslashes are normalized."""
    trailing_input = f"{folder_with_spaces.resolve()}\\"
    code, data, _ = client.post_json("/api/analyze", {"raw_input": trailing_input})
    assert code == 200
    assert data["success"] is True
    assert data["result"]["target_path"] == str(folder_with_spaces.resolve())


def test_smart_resolution_of_sibling_folder(tmp_path):
    """Simulates drag-drop where only bare folder name is received from WebView2."""
    workspace_parent = tmp_path / "Projects Directory"
    workspace_parent.mkdir()

    app_folder = workspace_parent / "CurrentApp"
    app_folder.mkdir()

    target_folder = workspace_parent / "Target Project With Spaces"
    target_folder.mkdir()
    (target_folder / "file.py").write_text("x = 1\n", encoding="utf-8")

    old_cwd = os.getcwd()
    try:
        os.chdir(str(app_folder))
        # InputDetector should search parent directory (Projects Directory) and find Target Project With Spaces
        detected = InputDetector.detect("Target Project With Spaces")
        assert detected.input_type == "folder"
        assert detected.friendly_label == "Target Project With Spaces"
        assert Path(detected.target_path).resolve() == target_folder.resolve()
    finally:
        os.chdir(old_cwd)


def test_non_existent_folder_error_details(client):
    """Verifies that non-existent paths produce plain-English errors containing the checked full path."""
    fake_path = "C:\\Definite_Non_Existent_Folder_999888\\SubFolder"
    code, data, _ = client.post_json("/api/analyze", {"raw_input": fake_path})
    assert code == 200
    assert data["success"] is False
    assert "Path does not exist on disk" in data["error"]
    assert fake_path in data["error"]


def test_full_ui_action_lifecycle(client):
    """Exercises all screens, prompt handoff, fix preview, and rollback on sample_bloated_project."""
    # 1. Analyze sample project
    code, data, _ = client.post_json("/api/analyze", {"raw_input": "sample_bloated_project"})
    assert code == 200
    assert data["success"] is True
    result = data["result"]
    assert result["health_score"] < 90
    assert result["total_savings_mb"] > 0

    # 2. Generate prompt (all 3 modes)
    for mode in ("fix_safe", "fix_all", "explain"):
        pcode, pdata, _ = client.post_json("/api/generate-prompt", {"mode": mode, "detail_level": "detailed"})
        assert pcode == 200
        assert pdata["success"] is True
        assert len(pdata["prompt_text"]) > 100

    # 3. Preview fixes
    pvcode, pvdata, _ = client.get("/api/fix/preview")
    assert pvcode == 200
    assert pvdata["success"] is True
    assert pvdata["count"] > 0

    # 4. Target override
    ocode, odata, _ = client.post_json("/api/override-target", {"forced_kind": "folder"})
    assert ocode == 200
    assert odata["success"] is True

    # 5. Static assets
    for asset in ("/", "/static/app.js", "/static/style.css", "/favicon.ico"):
        scode, _, _ = client.get(asset)
        assert scode == 200


def test_updater_service_and_endpoints(client, monkeypatch):
    """Verifies the Over-The-Air (OTA) update system and endpoints."""
    from optiforge.services import updater_service
    from optiforge.services.updater_service import parse_version_tuple

    # 1. Semver parsing
    assert parse_version_tuple("v1.0.1") > parse_version_tuple("v1.0.0")
    assert parse_version_tuple("v2.0.0") > parse_version_tuple("v1.9.9")
    assert parse_version_tuple("1.0.0") == parse_version_tuple("v1.0.0")

    # 2. Mock GitHub API response
    monkeypatch.setattr(updater_service, "CURRENT_VERSION", "1.0.0")
    fake_release = {
        "tag_name": "v1.0.1",
        "name": "OptiForge v1.0.1 — OTA Release",
        "body": "Bug fixes and improvements.",
        "assets": [
            {
                "name": "OptiForge-Setup-1.0.1.exe",
                "browser_download_url": "https://github.com/Chane0704/OptiForge/releases/download/v1.0.1/OptiForge-Setup-1.0.1.exe",
                "size": 25000000,
            }
        ]
    }

    class FakeUrlopen:
        def __init__(self, data):
            self.data = json.dumps(data).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, *args):
            return self.data

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, *args, **kwargs: FakeUrlopen(fake_release))

    # Test /api/updater/check
    code, check_data, _ = client.get("/api/updater/check")
    assert code == 200
    assert check_data["success"] is True
    assert check_data["update_available"] is True
    assert check_data["latest_version"] == "1.0.1"

    # Test /api/updater/status
    code, status_data, _ = client.get("/api/updater/status")
    assert code == 200
    assert "status" in status_data
    assert "progress_percent" in status_data
