"""End-to-end HTTP surface tests (real server thread, urllib client).

No real subprocesses: in M1 the action endpoints still raise
NotImplementedError, and the executor is never reached.
"""
import json
import os
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

import launcher_server
from config import load_config
from fakes import FakeExecutor
from launcher_server import LauncherApp, LauncherServer

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"


@pytest.fixture()
def base_url():
    cfg = load_config(REPO_CONFIG)
    # Fake executor + ready check: no real wsl/xcopy/web ever runs.
    app = LauncherApp(
        cfg,
        executor=FakeExecutor(),
        ready_check=lambda url, timeout: True,
    )
    server = LauncherServer(("127.0.0.1", 0), app)
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


def _post(url, path, payload=None, origin=None):
    data = json.dumps(payload or {}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if origin is not None:
        headers["Origin"] = origin
    req = urllib.request.Request(
        url + path, data=data, method="POST", headers=headers,
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _post_403(url, path, origin=None):
    """POST expecting a 403 cross-origin rejection."""
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(url, path, origin=origin)
    assert excinfo.value.code == 403
    return json.loads(excinfo.value.read().decode("utf-8"))


def test_get_root_returns_html(base_url):
    status, body = _get(base_url, "/")
    assert status == 200
    assert body.strip().startswith("<")


def test_get_root_serves_console_page(base_url):
    """M2: the served page must be the console (sidebar + iframe + poll)."""
    status, body = _get(base_url, "/")
    assert "System Control" in body
    assert "iframe" in body
    assert "/status" in body and "/config" in body


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
    assert data["log"]["label"] == "View Log"


def test_get_log_returns_log_list(base_url):
    """P17②: GET /log tails launcher_server.log + bridge logs (may be empty
    in a fresh test run — the shape is what matters)."""
    status, body = _get(base_url, "/log")
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is True
    assert isinstance(data["logs"], list)


def test_log_tail_reads_launcher_and_bridge_logs(tmp_path, monkeypatch):
    """P17②: log_tail tails *.log files in the launcher dir, last N lines."""
    monkeypatch.setattr(launcher_server, "HERE", tmp_path)
    (tmp_path / "launcher_server.log").write_text("l1\nl2\nl3\n", encoding="utf-8")
    (tmp_path / "bridge_headband.log").write_text("bridge line\n", encoding="utf-8")
    app = LauncherApp(load_config(REPO_CONFIG), executor=FakeExecutor(), ready_check=lambda u, t: True)

    logs = app.log_tail(lines=2)

    by_name = {f["source"]: f["lines"] for f in logs}
    assert "launcher_server.log" in by_name and "bridge_headband.log" in by_name
    assert by_name["launcher_server.log"] == ["l2", "l3"]  # tail lines=2


def test_start_system_via_http(base_url):
    status, body = _post(base_url, "/start-system", origin=base_url)
    assert status == 200
    assert body["ok"] is True
    # P41: message carries the LAN-forward note (portproxy always re-hung)
    assert "System started and ready" in body["message"]


def test_connect_when_system_stopped_via_http(base_url):
    status, body = _post(
        base_url, "/connect-device", {"device": "headband"}, origin=base_url,
    )
    assert status == 200
    assert body == {"ok": False, "message": "System not ready — start the system first"}


def test_unknown_path_404(base_url):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(base_url, "/nope", origin=base_url)
    assert excinfo.value.code == 404


def test_action_endpoints_are_post_only(base_url):
    """Contract pin for the real-device bug: action endpoints must reject
    GET (the frontend's bare api(path) became a GET and got 404 here)."""
    for path in ("/start-system", "/stop-system", "/restart-system", "/restart-web"):
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            _get(base_url, path)
        assert excinfo.value.code == 404


def test_restart_system_via_http(base_url):
    """③ P10: POST /restart-system while running → stop+start, ok + running."""
    _post(base_url, "/start-system", origin=base_url)
    status, body = _post(base_url, "/restart-system", origin=base_url)
    assert status == 200
    assert body["ok"] is True


def test_restart_system_when_stopped_rejected(base_url):
    status, body = _post(base_url, "/restart-system", origin=base_url)
    assert status == 200
    assert body == {"ok": False, "message": "System not running — nothing to restart"}


def test_post_without_origin_rejected(base_url):
    """Finding A: curl/script callers without Origin are denied."""
    body = _post_403(base_url, "/start-system", origin=None)
    assert body["message"] == "Cross-origin request rejected"


def test_post_evil_origin_rejected(base_url):
    """Finding A: an arbitrary webpage must not fire the action POSTs."""
    body = _post_403(base_url, "/stop-system", origin="http://evil.example.com")
    assert body["message"] == "Cross-origin request rejected"
    body = _post_403(base_url, "/start-system", origin="http://evil.example.com")
    assert body["message"] == "Cross-origin request rejected"


def test_main_honours_config_path_arg(capsys, monkeypatch):
    """main(sys.argv[1:]) must read the first arg as the config path (the
    argv slice means the path is argv[0], not argv[1])."""
    from launcher_server import main

    # Don't let main()'s real _setup_logging rewire sys.stdout / write the
    # repo log file during the test.
    monkeypatch.setattr(launcher_server, "_setup_logging", lambda: None)
    rc = main(["/nonexistent/o2_config.json"])
    assert rc == 1
    assert "config file not found" in capsys.readouterr().out


def test_pidfile_write_and_remove(tmp_path, monkeypatch):
    """P1: pidfile lifecycle — write on start, remove on shutdown, idempotent."""
    monkeypatch.setattr(launcher_server, "PID_FILE", tmp_path / "pid")
    launcher_server.write_pidfile()
    assert launcher_server.PID_FILE.exists()
    assert launcher_server.PID_FILE.read_text(encoding="utf-8") == str(os.getpid())

    launcher_server.remove_pidfile()
    assert not launcher_server.PID_FILE.exists()
    launcher_server.remove_pidfile()  # idempotent, never raises


def test_setup_logging_writes_file_when_stdout_none(tmp_path, monkeypatch):
    """P1: under pythonw sys.stdout is None — print() must still reach the
    launcher_server.log file (tee)."""
    monkeypatch.setattr(launcher_server, "LOG_FILE", tmp_path / "launcher_server.log")
    monkeypatch.setattr(sys, "stdout", None)
    launcher_server._setup_logging()
    print("hello-p1-log", flush=True)
    assert "hello-p1-log" in (tmp_path / "launcher_server.log").read_text(encoding="utf-8")


def test_service_messages_are_english():
    """P5: every user-facing {ok, message} value must be CJK-free."""
    import re

    cjk = re.compile(r"[一-鿿]")
    cfg = load_config(REPO_CONFIG)
    for dev in cfg["devices"].values():
        dev["verify_timeout_sec"] = 0
        dev["verify_poll_sec"] = 0
    cfg["wsl"]["ready_timeout_sec"] = 1
    cfg["wsl"]["ready_poll_sec"] = 0

    def messages(app):
        app._share_accessible = lambda: False
        results = [
            app.start_system(),       # WSL-not-ready error path
            app.stop_system(),
            app.restart_web(),
            app.restart_system(),     # ③ P10
            app.connect_device("headband"),
            app.connect_device("nope"),
            app.disconnect_device("thymio"),
        ]
        return [str(r.get("message", "")) for r in results]

    all_msgs = messages(LauncherApp(cfg, executor=FakeExecutor(detect_ok=False), ready_check=lambda u, t: True))
    # success paths too
    ok_cfg = load_config(REPO_CONFIG)
    for dev in ok_cfg["devices"].values():
        dev["verify_timeout_sec"] = 0
        dev["verify_poll_sec"] = 0
    ok_app = LauncherApp(ok_cfg, executor=FakeExecutor(), ready_check=lambda u, t: True)
    all_msgs += [ok_app.start_system()["message"], ok_app.connect_device("headband")["message"],
                 ok_app.disconnect_device("headband")["message"], ok_app.stop_system()["message"]]
    assert not cjk.search(" ".join(all_msgs)), all_msgs

    err = launcher_server.friendly_error(RuntimeError("WSL (Ubuntu) not ready"), "Start System")
    assert not cjk.search(err)


def test_shutdown_endpoint_stops_server_and_removes_pidfile(tmp_path, monkeypatch):
    """P1: POST /shutdown → 200, pidfile removed, serve_forever actually stops."""
    monkeypatch.setattr(launcher_server, "PID_FILE", tmp_path / "pid")
    launcher_server.write_pidfile()

    cfg = load_config(REPO_CONFIG)
    server = LauncherServer(
        ("127.0.0.1", 0),
        LauncherApp(cfg, executor=FakeExecutor(), ready_check=lambda u, t: True),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        status, body = _post(base, "/shutdown", origin=base)
        assert status == 200
        assert body == {"ok": True, "message": "Launcher service exited"}
        assert not launcher_server.PID_FILE.exists()  # removed by the handler
        t.join(timeout=5)
        assert not t.is_alive()  # serve_forever returned (response already sent)
    finally:
        server.server_close()
