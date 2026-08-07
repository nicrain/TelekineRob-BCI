"""M4 device chain — connect/disconnect bridges + usbipd with fake executor."""
from pathlib import Path

from config import load_config
from fakes import FakeExecutor
from launcher_server import LauncherApp

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"

VERIFY_WSL = 'wsl -d Ubuntu -e bash -lc "test -e /dev/ttyACM0 && echo ok"'


def _make_app(ex=None):
    cfg = load_config(REPO_CONFIG)
    # Tests must not sleep: zero the verify delays in every device config.
    for dev in cfg["devices"].values():
        dev["verify_delay_sec"] = 0
    ex = ex or FakeExecutor()
    app = LauncherApp(cfg, executor=ex, ready_check=lambda url, t: True)
    assert app.start_system()["ok"] is True  # system running → can connect
    return app, ex


def test_connect_bridge_success():
    app, ex = _make_app()
    result = app.connect_device("headband")

    assert result == {"ok": True, "message": "Headband 已连接"}
    assert app.state.devices["headband"] == "connected"
    assert "headband" in app._device_procs
    # The bridge is the LAST spawn (start_system spawned the 2 web services
    # first); command tokenized + cwd derived from ${sync.dst_root}.
    assert ex.spawn_calls[-1][0] == "python"
    assert ex.spawn_calls[-1][1] == "gpype_lsl_bridge.py"
    assert ex.spawn_cwds[-1].endswith("gtec_bridge")


def test_connect_bridge_runs_verify_cmd_when_configured():
    app, ex = _make_app()
    app.config["devices"]["headband"]["verify_cmd"] = VERIFY_WSL

    assert app.connect_device("headband")["ok"] is True

    assert any("ttyACM0" in c[-1] for c in ex.run_calls)


def test_connect_bridge_dies_during_verify():
    app, _ = _make_app(FakeExecutor(bridge_alive=False))
    result = app.connect_device("headband")

    assert result["ok"] is False
    assert "桥进程已退出" in result["message"]
    assert app.state.devices["headband"] == "error"


def test_connect_usbipd_success():
    app, ex = _make_app()
    result = app.connect_device("thymio")

    assert result == {"ok": True, "message": "Thymio 已连接"}
    assert app.state.devices["thymio"] == "connected"
    # attach ran, then the WSL ttyACM0 verify
    assert any(c[0] == "usbipd" and "attach" in c for c in ex.run_calls)
    assert any("ttyACM0" in c[-1] for c in ex.run_calls)


def test_connect_usbipd_attach_fails():
    app, _ = _make_app(FakeExecutor(usbipd_ok=False))
    result = app.connect_device("thymio")

    assert result["ok"] is False
    assert "usbipd attach 失败" in result["message"]
    assert app.state.devices["thymio"] == "error"


def test_connect_when_system_stopped_rejected():
    cfg = load_config(REPO_CONFIG)
    for dev in cfg["devices"].values():
        dev["verify_delay_sec"] = 0
    app = LauncherApp(cfg, executor=FakeExecutor(), ready_check=lambda u, t: True)
    # NOTE: no start_system() → system stays stopped
    result = app.connect_device("headband")

    assert result == {"ok": False, "message": "系统未就绪，请先启动系统"}


def test_connect_unknown_device():
    app, _ = _make_app()
    assert app.connect_device("nope") == {"ok": False, "message": "未知设备: nope"}


def test_connect_idempotent_no_second_spawn():
    app, ex = _make_app()
    assert app.connect_device("headband")["ok"] is True
    spawn_before = len(ex.spawn_calls)

    second = app.connect_device("headband")

    assert second["ok"] is True
    assert len(ex.spawn_calls) == spawn_before


def test_disconnect_bridge_terminates():
    app, ex = _make_app()
    app.connect_device("headband")
    proc = app._device_procs["headband"]

    result = app.disconnect_device("headband")

    assert result == {"ok": True, "message": "Headband 已断开"}
    assert app.state.devices["headband"] == "disconnected"
    assert "headband" not in app._device_procs
    assert proc.poll() is not None  # terminated


def test_disconnect_usbipd_runs_detach():
    app, ex = _make_app()
    app.connect_device("thymio")

    assert app.disconnect_device("thymio")["ok"] is True
    assert app.state.devices["thymio"] == "disconnected"
    assert any(c[0] == "usbipd" and "detach" in c for c in ex.run_calls)


def test_disconnect_when_already_disconnected_idempotent():
    app, _ = _make_app()
    assert app.disconnect_device("thymio") == {"ok": True, "message": "Thymio 已断开"}
