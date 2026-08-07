"""M5 status display — payload shape + proc-health reconciliation (§4)."""
from pathlib import Path

from config import load_config
from fakes import FakeExecutor
from launcher_server import LauncherApp

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"


def _make_app():
    cfg = load_config(REPO_CONFIG)
    for dev in cfg["devices"].values():
        dev["verify_delay_sec"] = 0
    app = LauncherApp(cfg, executor=FakeExecutor(), ready_check=lambda u, t: True)
    assert app.start_system()["ok"] is True
    return app


def test_status_reflects_connected_device():
    app = _make_app()
    app.connect_device("headband")
    payload = app.status()
    assert payload["devices"]["headband"]["state"] == "connected"


def test_status_flags_dead_bridge_as_error():
    """§4: 断桥后状态变红/灰，不残留"已连接"."""
    app = _make_app()
    app.connect_device("headband")
    app._device_procs["headband"].kill()  # bridge dies spontaneously

    payload = app.status()

    assert payload["devices"]["headband"]["state"] == "error"
    assert payload["devices"]["headband"]["message"] == "桥进程已退出"


def test_status_system_running_message_present():
    app = _make_app()
    payload = app.status()
    assert payload["system"]["state"] == "running"
    assert payload["system"]["message"] == "系统已就绪"
    assert set(payload["devices"]) == {"headband", "hybrid", "thymio"}
