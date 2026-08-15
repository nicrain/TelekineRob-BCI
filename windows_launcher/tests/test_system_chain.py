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
    for dev in cfg["devices"].values():
        dev["reconcile_sec"] = 0  # P10②
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


def test_restart_system_stops_then_starts():
    """③ P10: /restart-system = stop then start — WSL is terminated and the
    web services re-spawned, ending in running."""
    app, ex = _make_app()
    assert app.start_system()["ok"] is True
    spawn_before = len(ex.spawn_calls)

    result = app.restart_system()

    assert result["ok"] is True
    assert app.state.system == "running"
    assert any(c[:2] == ["wsl", "--terminate"] for c in ex.run_calls)  # stop ran
    assert len(ex.spawn_calls) == spawn_before + 2                      # re-spawned


def test_restart_system_when_stopped_rejected():
    """③ P10: nothing running → no stop+start, clean rejection."""
    app, _ = _make_app()

    result = app.restart_system()

    assert result == {"ok": False, "message": "System not running — nothing to restart"}
    assert app.state.system == "stopped"


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


# --- P38: web idempotency — zombie vite leak + port drift -----------------

def test_start_system_precleans_leftover_web():
    """P38①: start_system runs the WSL stop_cmd (pkill app.main + vite)
    BEFORE spawning the web services — a retry frees 5173/8010 first, so
    nothing stacks up. Order: detect (systemctl) → sync (robocopy ×2) →
    pre-clean (pkill) → spawns."""
    app, ex = _make_app()
    assert app.start_system()["ok"] is True
    pkill_idx = next(i for i, c in enumerate(ex.run_calls) if "pkill" in c[-1])
    assert pkill_idx >= 3                    # after detect + 2 syncs
    assert ex.run_calls[pkill_idx][-1].count("pkill") == 2   # app.main + npm run dev
    assert len(ex.spawn_calls) == 2


def test_start_system_failure_cleans_web_procs():
    """P38③: when start fails (web not ready), the web processes spawned THIS
    round are terminated — no zombie vite leaks into a retry."""
    app, ex = _make_app(ready=False)
    result = app.start_system()
    assert result["ok"] is False
    assert len(ex.spawn_calls) == 2
    assert app._web_procs == []              # cleaned up on failure


def test_restart_web_failure_cleans_web_procs():
    """P38③: restart_web failure also clears this round's web processes."""
    app, ex = _make_app()
    assert app.start_system()["ok"] is True
    app._ready_check = lambda url, t: False  # force the respawn to time out
    result = app.restart_web()
    assert result["ok"] is False
    assert app._web_procs == []              # new spawns cleaned on failure


def test_frontend_cmd_pins_5173_strict():
    """P38②: frontend_cmd pins vite to 5173 with --strictPort — an occupied
    port fails visibly instead of silently drifting to 5174+ (which the
    hardcoded localhost:5173 probe could never reach)."""
    cfg = load_config(REPO_CONFIG)
    cmd = cfg["web"]["frontend_cmd"]
    assert "--port 5173" in cmd
    assert "--strictPort" in cmd


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
