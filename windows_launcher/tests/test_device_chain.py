"""M4 device chain — connect/disconnect bridges + usbipd with fake executor."""
from pathlib import Path

import launcher_server
from commands import CompletedCommand, build_python_script_cmd
from config import load_config
from fakes import FakeExecutor
from launcher_server import LauncherApp

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"


def _make_app(ex=None):
    cfg = load_config(REPO_CONFIG)
    # Tests must not sleep: zero the LSL verify timeout/poll for every device.
    for dev in cfg["devices"].values():
        dev["verify_timeout_sec"] = 0
        dev["verify_poll_sec"] = 0
        dev["reconcile_sec"] = 0  # P10②: usbipd reconcile fires every status()
        dev["open_ide_timeout_sec"] = 0  # P13①: no 120s background wait in tests
    ex = ex or FakeExecutor()
    app = LauncherApp(cfg, executor=ex, ready_check=lambda url, t: True)
    assert app.start_system()["ok"] is True  # system running → can connect
    return app, ex


def test_connect_bridge_success():
    """P8b: spawn mode (hybrid) — bridge up + LSL stream resolves → green."""
    app, ex = _make_app()
    result = app.connect_device("hybrid")

    assert result == {"ok": True, "message": "HybridBlack connected"}
    assert app.state.devices["hybrid"] == "connected"
    assert "hybrid" in app._device_procs
    # The bridge is the LAST spawn (start_system spawned the 2 web services
    # first); command is [python_cmd, script], cwd derived from ${sync.dst_root}.
    assert ex.spawn_calls[-1][0] == "python"
    assert ex.spawn_calls[-1][1] == "unicornpy_lsl_bridge.py"
    assert ex.spawn_cwds[-1].endswith("gtec_bridge")


def test_connect_bridge_probes_lsl_stream():
    """P8b: connect runs the LSL probe — green means the stream resolved,
    not that the process stayed alive."""
    app, ex = _make_app()
    assert app.connect_device("hybrid")["ok"] is True
    assert any(any("lsl_probe.py" in part for part in c) for c in ex.run_calls)


def test_connect_bridge_fails_when_no_lsl_stream():
    """P8b: device off → probe never finds the stream → timeout + error,
    no false green."""
    app, _ = _make_app(FakeExecutor(lsl_state="not-found"))
    result = app.connect_device("hybrid")

    assert result["ok"] is False
    assert "no LSL stream" in result["message"]
    assert app.state.devices["hybrid"] == "error"


def test_connect_bridge_terminates_stale_proc():
    """P11-fix①: a bridge left over from a stalled grey-out must be
    terminated before the reconnect spawns a new one — otherwise the old
    process leaks and holds the device ("device in use") / double outlet."""
    app, ex = _make_app()
    assert app.connect_device("hybrid")["ok"] is True
    old_proc = app._device_procs["hybrid"]
    spawn_before = len(ex.spawn_calls)

    # device goes off → reconcile grey (bridge kept alive, process leaks)
    app._lsl_state = lambda dev: "stalled"
    payload = app.status()
    assert payload["devices"]["hybrid"]["state"] == "disconnected"
    assert app._device_procs["hybrid"].poll() is None  # still alive (design)

    # operator reconnects → the stale proc is terminated first, then respawn
    app._lsl_state = lambda dev: "alive"
    result = app.connect_device("hybrid")

    assert result["ok"] is True
    assert old_proc.poll() is not None            # old process terminated
    assert app._device_procs["hybrid"] is not old_proc
    assert len(ex.spawn_calls) == spawn_before + 1  # exactly one new bridge


def test_connect_usbipd_success():
    app, ex = _make_app()
    app._thymio_attached = lambda dev: False  # device NOT already attached
    result = app.connect_device("thymio")

    assert result == {"ok": True, "message": "Thymio connected"}
    assert app.state.devices["thymio"] == "connected"
    # attach ran, then the WSL ttyACM0 verify
    assert any(c[0] == "usbipd" and "attach" in c for c in ex.run_calls)
    assert any("ttyACM0" in c[-1] for c in ex.run_calls)


def test_connect_usbipd_idempotent_when_already_attached():
    """P10②: usbipd attach survives launcher restarts — connect skips the
    attach (would fail with "already attached") and goes straight green."""
    app, ex = _make_app()
    # default FakeExecutor verify_ok=True → already attached
    result = app.connect_device("thymio")

    assert result == {"ok": True, "message": "Thymio connected"}
    assert app.state.devices["thymio"] == "connected"
    assert not any(c[0] == "usbipd" for c in ex.run_calls)  # attach skipped


def test_connect_usbipd_attach_fails():
    app, _ = _make_app(FakeExecutor(usbipd_ok=False))
    app._thymio_attached = lambda dev: False  # force the attach path
    result = app.connect_device("thymio")

    assert result["ok"] is False
    assert "usbipd attach failed" in result["message"]
    assert app.state.devices["thymio"] == "error"


def test_connect_when_system_stopped_rejected():
    cfg = load_config(REPO_CONFIG)
    for dev in cfg["devices"].values():
        dev["verify_timeout_sec"] = 0
        dev["verify_poll_sec"] = 0
    app = LauncherApp(cfg, executor=FakeExecutor(), ready_check=lambda u, t: True)
    # NOTE: no start_system() → system stays stopped
    result = app.connect_device("headband")

    assert result == {"ok": False, "message": "System not ready — start the system first"}


def test_connect_unknown_device():
    app, _ = _make_app()
    assert app.connect_device("nope") == {"ok": False, "message": "Unknown device: nope"}


def test_connect_idempotent_no_second_spawn():
    app, ex = _make_app()
    assert app.connect_device("hybrid")["ok"] is True
    spawn_before = len(ex.spawn_calls)

    second = app.connect_device("hybrid")

    assert second["ok"] is True
    assert len(ex.spawn_calls) == spawn_before


def test_disconnect_bridge_terminates():
    app, ex = _make_app()
    app.connect_device("hybrid")
    proc = app._device_procs["hybrid"]

    result = app.disconnect_device("hybrid")

    assert result == {"ok": True, "message": "HybridBlack disconnected"}
    assert app.state.devices["hybrid"] == "disconnected"
    assert "hybrid" not in app._device_procs
    assert proc.poll() is not None  # terminated


def test_disconnect_usbipd_runs_detach():
    app, ex = _make_app()
    app._thymio_attached = lambda dev: False  # attach actually runs first
    app.connect_device("thymio")

    assert app.disconnect_device("thymio")["ok"] is True
    assert app.state.devices["thymio"] == "disconnected"
    assert any(c[0] == "usbipd" and "detach" in c for c in ex.run_calls)


def test_disconnect_when_already_disconnected_idempotent():
    app, _ = _make_app()
    assert app.disconnect_device("thymio") == {"ok": True, "message": "Thymio disconnected"}


# --- P13①: open_in_ide connect timeout ----------------------------------

def test_open_in_ide_timeout_config_is_generous():
    """The operator runs the headband bridge in VS Code by hand — the
    open_in_ide connect must give them 120s, not the 30s spawn-mode timeout."""
    cfg = load_config(REPO_CONFIG)
    assert cfg["devices"]["headband"].get("open_ide_timeout_sec", 120) >= 120


def test_wait_lsl_background_does_not_override_disconnect():
    """P13①: if the operator disconnects while the background wait is still
    running, a late success must not flip the device back to green."""
    app, _ = _make_app()
    app.state.set_device("headband", "connecting", "waiting for LSL stream")
    assert app.disconnect_device("headband")["ok"] is True  # explicit disconnect

    app._wait_lsl_background("headband", app.config["devices"]["headband"], 0, 0)

    assert app.state.devices["headband"] == "disconnected"


# --- P8d: open_in_ide mode (headband) ------------------------------------

def test_connect_open_in_ide_opens_script_and_prompts():
    """connect runs open_cmd (VS Code CLI) and returns the press-Run prompt;
    the state is 'waiting for LSL stream' (busy) until the probe lands."""
    app, ex = _make_app()
    result = app.connect_device("headband")

    assert result["ok"] is True
    assert "press Run (F5)" in result["message"]
    assert any(c[0] == "code" for c in ex.run_calls)  # VS Code CLI open
    assert app.state.devices["headband"] in ("connecting", "connected")


def test_wait_lsl_background_sets_connected():
    app, _ = _make_app()  # lsl_state="alive" by default
    app.state.set_device("headband", "connecting", "waiting for LSL stream")
    app._wait_lsl_background("headband", app.config["devices"]["headband"], 0, 0)
    assert app.state.devices["headband"] == "connected"


def test_wait_lsl_background_times_out_to_error():
    app, _ = _make_app(FakeExecutor(lsl_state="not-found"))
    app.state.set_device("headband", "connecting", "waiting for LSL stream")
    app._wait_lsl_background("headband", app.config["devices"]["headband"], 0, 0)
    assert app.state.devices["headband"] == "error"
    assert "no LSL stream" in app.state.device_msgs["headband"]


def test_open_in_ide_falls_back_when_code_missing():
    """code not on PATH → the configured default-opener fallback runs."""
    app, ex = _make_app()
    dev = app.config["devices"]["headband"]
    original_run = ex.run

    def run(cmd, **kw):
        if cmd and cmd[0] == "code":
            raise FileNotFoundError("code")
        return original_run(cmd, **kw)

    ex.run = run
    app._open_script(dev)

    assert any(c[0] == "cmd" and "start" in c for c in ex.run_calls)


def test_disconnect_ide_returns_vscode_message():
    """We cannot stop a bridge running in VS Code — reset + prompt."""
    app, _ = _make_app()
    app.state.set_device("headband", "connected", "Connected")
    result = app.disconnect_device("headband")

    assert result == {"ok": True, "message": "Stop the bridge in VS Code"}
    assert app.state.devices["headband"] == "disconnected"


# --- P8a / P8c -----------------------------------------------------------

def test_connect_bridge_logs_to_file(tmp_path, monkeypatch):
    """The spawned bridge's output is redirected to bridge_<device>.log."""
    monkeypatch.setattr(launcher_server, "HERE", tmp_path)
    app, ex = _make_app()
    app.connect_device("hybrid")

    assert ex.spawn_logs[-1]  # a log path was passed to spawn
    assert str(ex.spawn_logs[-1]).endswith("bridge_hybrid.log")
    assert "connect hybrid" in (tmp_path / "bridge_hybrid.log").read_text(encoding="utf-8")


def test_bridge_command_uses_python_cmd():
    """python_cmd is machine-local config — a venv path is used as-is."""
    cmd = build_python_script_cmd(r"C:\venvs\robot\python.exe", "unicornpy_lsl_bridge.py")
    assert cmd == [r"C:\venvs\robot\python.exe", "unicornpy_lsl_bridge.py"]
    assert build_python_script_cmd("python", "x.py") == ["python", "x.py"]
