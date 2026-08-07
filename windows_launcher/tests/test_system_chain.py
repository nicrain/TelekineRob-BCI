"""M3 system chain — start/stop/restart with a fake executor + ready check."""
from pathlib import Path

from config import load_config
from fakes import FakeExecutor
from launcher_server import LauncherApp

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"


def _make_app(*, ready=True, detect_ok=True, sync_ok=True):
    cfg = load_config(REPO_CONFIG)
    ex = FakeExecutor(detect_ok=detect_ok, sync_ok=sync_ok)
    app = LauncherApp(cfg, executor=ex, ready_check=lambda url, t: ready)
    return app, ex


def test_start_system_success_sequence():
    app, ex = _make_app()
    result = app.start_system()

    assert result == {"ok": True, "message": "系统已启动并就绪"}
    assert app.state.system == "running"
    # order: wsl detect → sync dir1 → sync dir2 → spawn backend/frontend
    assert ex.run_calls[0][-1].endswith("echo ok")
    assert ex.run_calls[1][0] == "xcopy"
    assert ex.run_calls[2][0] == "xcopy"
    assert len(ex.spawn_calls) == 2
    assert "python -m app.main" in ex.spawn_calls[0][-1]
    assert "npm run dev" in ex.spawn_calls[1][-1]


def test_start_system_wsl_down_fails_before_spawn():
    app, ex = _make_app(detect_ok=False)
    result = app.start_system()

    assert result["ok"] is False
    assert "WSL" in result["message"]
    assert app.state.system == "error"
    assert ex.spawn_calls == []


def test_start_system_ready_timeout_reports_error():
    app, ex = _make_app(ready=False)
    result = app.start_system()

    assert result["ok"] is False
    assert "未就绪" in result["message"]
    assert app.state.system == "error"


def test_start_system_sync_failure_reports_error():
    app, ex = _make_app(sync_ok=False)
    result = app.start_system()

    assert result["ok"] is False
    assert "同步" in result["message"]
    assert app.state.system == "error"


def test_start_system_idempotent():
    app, ex = _make_app()
    assert app.start_system()["ok"] is True
    run_before = len(ex.run_calls)

    second = app.start_system()

    assert second == {"ok": True, "message": "系统已在运行或启动中"}
    assert len(ex.run_calls) == run_before  # no re-work


def test_stop_system_terminates_wsl_and_resets_devices():
    app, ex = _make_app()
    app.start_system()
    # fake a connected bridge so the device proc list is non-empty
    app._device_procs["headband"] = ex.spawn(["python", "gpype_lsl_bridge.py"])

    result = app.stop_system()

    assert result["ok"] is True
    assert app.state.system == "stopped"
    assert ex.run_calls[-1][:2] == ["wsl", "--terminate"]
    assert app.state.devices["headband"] == "disconnected"
    assert app.state.device_msgs["headband"] == ""


def test_stop_system_idempotent_when_already_stopped():
    app, _ = _make_app()
    result = app.stop_system()
    assert result == {"ok": True, "message": "系统已停止"}


def test_restart_web_respawns_services():
    app, ex = _make_app()
    app.start_system()
    spawn_before = len(ex.spawn_calls)

    result = app.restart_web()

    assert result["ok"] is True
    assert app.state.system == "running"
    assert len(ex.spawn_calls) == spawn_before + 2
    # stop_cmd (pkill) ran inside WSL before respawning
    assert any("pkill" in c[-1] for c in ex.run_calls)
