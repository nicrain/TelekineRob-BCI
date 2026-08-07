"""End-to-end HTTP surface tests (real server thread, urllib client).

No real subprocesses: in M1 the action endpoints still raise
NotImplementedError, and the executor is never reached.
"""
import json
import threading
import urllib.request
from pathlib import Path

import pytest

from config import load_config
from launcher_server import LauncherApp, LauncherServer

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"


@pytest.fixture()
def base_url():
    cfg = load_config(REPO_CONFIG)
    server = LauncherServer(("127.0.0.1", 0), LauncherApp(cfg))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _get(url, path):
    with urllib.request.urlopen(url + path, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


def _post(url, path, payload=None):
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url + path, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_get_root_returns_html(base_url):
    status, body = _get(base_url, "/")
    assert status == 200
    assert body.strip().startswith("<")


def test_get_status_initial_shape(base_url):
    status, body = _get(base_url, "/status")
    assert status == 200
    data = json.loads(body)
    assert data["system"]["state"] == "stopped"
    assert set(data["devices"]) == {"headband", "hybrid", "thymio"}
    assert all(d["state"] == "disconnected" for d in data["devices"].values())


def test_get_config_returns_sidebar(base_url):
    status, body = _get(base_url, "/config")
    data = json.loads(body)
    assert data["groups"]
    assert data["log"]["label"] == "查看日志"


def test_action_stub_returns_not_implemented(base_url):
    status, body = _post(base_url, "/start-system")
    assert status == 200
    assert body == {"ok": False, "message": "该功能尚未开通"}


def test_connect_stub_returns_not_implemented(base_url):
    status, body = _post(base_url, "/connect-device", {"device": "headband"})
    assert body == {"ok": False, "message": "该功能尚未开通"}


def test_unknown_path_404(base_url):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(base_url, "/nope")
    assert excinfo.value.code == 404
