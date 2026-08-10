"""M3 system chain — start/stop/restart with a fake executor + ready check."""
from pathlib import Path

from config import load_config
from fakes import FakeExecutor
from launcher_server import LauncherApp

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"


def _make_app(*, ready=True, detect_ok=True, sync_ok=True, **kw):
    cfg = load_config(REPO_CONFIG)
    # Tests must not sleep for the real WSL-boot timeout: ~1s deadline,
    # zero poll interval.
    cfg["wsl"]["ready_timeout_sec"] = 1
    cfg["wsl"]["ready_poll_sec"] = 0
    ex = FakeExecutor(detect_ok=detect_ok, sync_ok=sync_ok, **kw)
    app = LauncherApp(cfg, executor=ex, ready_check=lambda url, t: ready)
    return app, ex


def test_start_system_success_sequence():
    app, ex = _make_app()
    result = app.start_system()

    assert result == {"ok": True, "message": "System started and ready"}
    assert app.state.system == "running"
    # order: wsl readiness (systemctl) → sync windows_launcher → gtec_bridge
    assert "is-system-running" in ex.run_calls[0][-1]
    assert ex.run_calls[1][0] == "robocopy"
    assert ex.run_calls[2][0] == "robocopy"
    # finding C: config.json excluded only from the windows_launcher item
    assert "config.json" in ex.run_calls[1]
    assert "config.json" not in ex.run_calls[2]
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
    assert "not ready" in result["message"]
    assert app.state.system == "error"


def test_start_system_sync_failure_reports_error():
    app, ex = _make_app(sync_ok=False)
    result = app.start_system()

    assert result["ok"] is False
    assert "sync of" in result["message"]
    assert app.state.system == "error"


def test_start_system_idempotent():
    app, ex = _make_app()
    assert app.start_system()["ok"] is True
    run_before = len(ex.run_calls)

    second = app.start_system()

    assert second == {"ok": True, "message": "System already starting or running"}
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
    assert result == {"ok": True, "message": "System stopped"}


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


def test_start_system_accepts_degraded_systemd():
    """O31: real systemd reports degraded with exit code 1 — the OUTPUT is
    authoritative, so degraded@exit1 must still mean "booted and ready"."""
    app, _ = _make_app(systemd_state="degraded")
    result = app.start_system()
    assert result["ok"] is True
    assert app.state.system == "running"


def test_start_system_survives_hanging_probe():
    """O32: a single probe that times out must not abort the poll — the
    loop keeps polling and succeeds once a later probe answers."""
    app, _ = _make_app(hang_probes=2)
    result = app.start_system()
    assert result["ok"] is True
    assert app.state.system == "running"
    # the two hanging probes were still issued before the success
    assert sum("is-system-running" in c[-1] for c in app.executor.run_calls) >= 3


def test_start_system_falls_back_to_wsl_share_access():
    """No systemd (or not up yet) → the \\\\wsl$ share being reachable is
    enough for readiness."""
    app, _ = _make_app(detect_ok=False)
    app._share_accessible = lambda: True  # \\wsl$ repo share becomes reachable
    result = app.start_system()
    assert result["ok"] is True
    assert app.state.system == "running"


def test_start_system_wsl_not_ready_times_out():
    """systemctl keeps saying 'starting' and the share never appears."""
    app, ex = _make_app(detect_ok=False)
    app._share_accessible = lambda: False
    result = app.start_system()
    assert result["ok"] is False
    assert "not ready" in result["message"]
    assert "WSL" in result["message"]
    assert ex.spawn_calls == []
