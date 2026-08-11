"""M5 status display — payload shape + proc-health reconciliation (§4)."""
from pathlib import Path

from config import load_config
from fakes import FakeExecutor
from launcher_server import LauncherApp

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"


def _make_app(ex=None):
    cfg = load_config(REPO_CONFIG)
    for dev in cfg["devices"].values():
        dev["verify_timeout_sec"] = 0
        dev["verify_poll_sec"] = 0
        dev["reconcile_sec"] = 0  # P10②: usbipd reconcile fires every status()
    app = LauncherApp(cfg, executor=ex or FakeExecutor(), ready_check=lambda u, t: True)
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
    app._lsl_state = lambda dev: "not-found"  # operator stopped the VS Code bridge

    payload = app.status()

    assert payload["devices"]["headband"]["state"] == "disconnected"


def test_status_system_running_message_present():
    app = _make_app()
    payload = app.status()
    assert payload["system"]["state"] == "running"
    assert payload["system"]["message"] == "System ready"
    assert set(payload["devices"]) == {"headband", "hybrid", "thymio"}


# --- P10②: usbipd reconcile --------------------------------------------

def test_reconcile_thymio_connected_when_already_attached():
    """usbipd attach survives launcher restarts: a device attached on the
    hardware shows green right after start, no connect click needed."""
    app = _make_app()

    payload = app.status()

    assert payload["devices"]["thymio"]["state"] == "connected"


def test_reconcile_thymio_disconnected_when_detached():
    """The verify probe stops hitting (ttyACM0 gone) → a stale green falls
    back to grey."""
    app = _make_app(ex=FakeExecutor(verify_ok=False))
    app.state.set_device("thymio", "connected", "Connected")

    payload = app.status()

    assert payload["devices"]["thymio"]["state"] == "disconnected"


def test_reconcile_usbipd_skipped_when_system_down():
    """P10② guard: probing ttyACM0 would boot WSL from a stopped system —
    reconcile must no-op (and leave the initial state) while system stopped."""
    cfg = load_config(REPO_CONFIG)
    for dev in cfg["devices"].values():
        dev["verify_timeout_sec"] = 0
        dev["verify_poll_sec"] = 0
        dev["reconcile_sec"] = 0
    app = LauncherApp(cfg, executor=FakeExecutor(), ready_check=lambda u, t: True)
    app.state.set_device("thymio", "connected", "Connected")  # system STOPPED

    payload = app.status()

    assert payload["system"]["state"] == "stopped"
    assert payload["devices"]["thymio"]["state"] == "connected"  # untouched


# --- P11: LSL liveness reconcile (unified IDE + spawn) ------------------

def test_reconcile_spawn_bridge_grey_when_stream_stalled():
    """P11: spawn mode — the bridge process is ALIVE but the stream is empty
    (device off, bridge keeps publishing) → grey, not the old stale green."""
    app = _make_app()
    assert app.connect_device("hybrid")["ok"] is True
    app._lsl_state = lambda dev: "stalled"

    payload = app.status()

    assert payload["devices"]["hybrid"]["state"] == "disconnected"


def test_reconcile_spawn_bridge_grey_when_stream_not_found():
    app = _make_app()
    assert app.connect_device("hybrid")["ok"] is True
    app._lsl_state = lambda dev: "not-found"

    payload = app.status()

    assert payload["devices"]["hybrid"]["state"] == "disconnected"


def test_reconcile_stays_green_when_stream_alive():
    app = _make_app()
    assert app.connect_device("hybrid")["ok"] is True
    app._lsl_state = lambda dev: "alive"

    payload = app.status()

    assert payload["devices"]["hybrid"]["state"] == "connected"


def test_reconcile_upgrades_stalled_to_connected_when_stream_returns():
    """P11-fix②: a device greyed out by stall whose bridge self-recovers
    (unicornpy O4 / gpype P10 watchdog) auto-greens — no manual reconnect."""
    app = _make_app()
    assert app.connect_device("hybrid")["ok"] is True
    app._lsl_state = lambda dev: "stalled"
    assert app.status()["devices"]["hybrid"]["state"] == "disconnected"

    app._lsl_state = lambda dev: "alive"  # device came back
    app._last_lsl_check["hybrid"] = 0     # skip the 10s liveness throttle
    payload = app.status()

    assert payload["devices"]["hybrid"]["state"] == "connected"


def test_disconnect_clears_stalled_no_auto_recover():
    """P11-fix②: an EXPLICIT disconnect must never auto-green again, even if
    the stream is alive afterwards (the operator said disconnect)."""
    app = _make_app()
    assert app.connect_device("hybrid")["ok"] is True
    assert app.disconnect_device("hybrid")["ok"] is True

    app._lsl_state = lambda dev: "alive"
    payload = app.status()

    assert payload["devices"]["hybrid"]["state"] == "disconnected"


def test_disconnect_after_stall_clears_auto_recover():
    """P11-fix②: disconnecting a stall-greyed device cancels the pending
    auto-recover — the operator disconnecting it means "stop, stay off"."""
    app = _make_app()
    assert app.connect_device("hybrid")["ok"] is True
    app._lsl_state = lambda dev: "stalled"
    assert app.status()["devices"]["hybrid"]["state"] == "disconnected"

    assert app.disconnect_device("hybrid")["ok"] is True
    app._lsl_state = lambda dev: "alive"
    payload = app.status()

    assert payload["devices"]["hybrid"]["state"] == "disconnected"


# --- P10①: system health reconcile -------------------------------------

def test_system_health_error_when_web_down():
    """running but the frontend stops answering → the system is no longer
    usable: report error + a human action hint."""
    app = _make_app()
    app._last_system_health_check = 0  # force the probe now
    app._ready_check = lambda url, t: False

    payload = app.status()

    assert payload["system"]["state"] == "error"
    assert "web service" in payload["system"]["message"]


def test_system_health_stays_running_when_web_up():
    app = _make_app()
    app._last_system_health_check = 0

    payload = app.status()

    assert payload["system"]["state"] == "running"


def test_system_health_check_throttled():
    """The probe is throttled (health_interval_sec): a recent check skips
    the HTTP round-trip on this 1.5 s poll."""
    import time

    app = _make_app()
    app._last_system_health_check = time.time()  # just probed
    app._ready_check = lambda url, t: (_ for _ in ()).throw(
        AssertionError("health probe should be throttled")
    )

    payload = app.status()

    assert payload["system"]["state"] == "running"
