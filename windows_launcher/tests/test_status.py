"""M5 status display — payload shape + proc-health reconciliation (§4)."""
from pathlib import Path

from config import load_config
from fakes import FakeExecutor
from launcher_server import LauncherApp

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"


def _make_app():
    cfg = load_config(REPO_CONFIG)
    for dev in cfg["devices"].values():
        dev["verify_timeout_sec"] = 0
        dev["verify_poll_sec"] = 0
    app = LauncherApp(cfg, executor=FakeExecutor(), ready_check=lambda u, t: True)
    assert app.start_system()["ok"] is True
    return app


def test_status_reflects_connected_device():
    app = _make_app()
    app.connect_device("hybrid")
    payload = app.status()
    assert payload["devices"]["hybrid"]["state"] == "connected"


def test_status_flags_dead_bridge_as_error():
    """§4: spawn mode — the bridge process dies → red, not stale green."""
    app = _make_app()
    app.connect_device("hybrid")
    app._device_procs["hybrid"].kill()  # bridge dies spontaneously

    payload = app.status()

    assert payload["devices"]["hybrid"]["state"] == "error"
    assert payload["devices"]["hybrid"]["message"] == "bridge process exited"


def test_status_ide_device_falls_back_when_lsl_lost():
    """P8d: IDE mode has no launcher process — the LSL stream is the truth;
    when it disappears the device falls back to grey."""
    app = _make_app()
    app.state.set_device("headband", "connected", "Connected")
    app._lsl_found = lambda dev: False  # operator stopped the VS Code bridge

    payload = app.status()

    assert payload["devices"]["headband"]["state"] == "disconnected"


def test_status_system_running_message_present():
    app = _make_app()
    payload = app.status()
    assert payload["system"]["state"] == "running"
    assert payload["system"]["message"] == "System ready"
    assert set(payload["devices"]) == {"headband", "hybrid", "thymio"}
