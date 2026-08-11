"""P10④: gpype bridge data-flow watchdog + pipeline rebuild.

The pure logic (DataWatchdog stall detection, BridgeController rebuild/
retry) lives in gpype_lsl_bridge.py and imports gpype/pylsl lazily, so it
runs here on macOS with a fake api — no SDK, no real device.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtec_bridge"))
import gpype_lsl_bridge as bridge


class FakeBridgeApi:
    """Mimics GpypeBridge's surface: build/start/teardown/data_arrived.

    ``reconnect_failures`` makes the first N builds of EACH rebuild cycle
    fail (per-teardown cycle, like the real device still being gone/in use),
    so tests can prove backoff growth and reset per cycle.
    """

    def __init__(self, data_flowing: bool = True, reconnect_failures: int = 0):
        self.events: list[str] = []          # call order, e.g. build→start
        self.data_flowing = data_flowing
        self.reconnect_failures = reconnect_failures
        self._seen_teardown = False
        self._cycle_builds = 0

    def build(self) -> None:
        self.events.append("build")
        self._cycle_builds += 1
        if self._seen_teardown and self._cycle_builds <= self.reconnect_failures:
            raise RuntimeError("device busy")

    def start(self) -> None:
        self.events.append("start")

    def teardown(self) -> None:
        self.events.append("teardown")
        self._seen_teardown = True
        self._cycle_builds = 0

    def data_arrived(self) -> bool:
        self.events.append("data")
        return self.data_flowing


class RecordingSleep:
    """Records sleeps; optionally raises KeyboardInterrupt (Ctrl+C / test end)."""

    def __init__(self, calls_before_stop=None):
        self.slept: list[float] = []
        self.calls = 0
        self.calls_before_stop = calls_before_stop

    def __call__(self, secs: float) -> None:
        self.calls += 1
        self.slept.append(secs)
        if self.calls_before_stop is not None and self.calls >= self.calls_before_stop:
            raise KeyboardInterrupt


# --- DataWatchdog (pure) ------------------------------------------------

def test_watchdog_stalls_after_inactivity_and_resets():
    t = [0.0]
    wd = bridge.DataWatchdog(stall_sec=5, now_fn=lambda: t[0])

    assert wd.stalled() is False        # just started
    t[0] = 4.9
    assert wd.stalled() is False
    t[0] = 5.0
    assert wd.stalled() is True         # no data for >= 5s
    wd.mark_data()
    assert wd.stalled() is False        # a sample resets the clock
    t[0] = 9.9
    assert wd.stalled() is False


# --- BridgeController: rebuild trigger --------------------------------

def test_no_rebuild_while_data_flows():
    """Samples keep arriving → watchdog stays fresh → zero rebuilds."""
    api = FakeBridgeApi(data_flowing=True)
    sleep = RecordingSleep(calls_before_stop=3)  # stop after 3 poll loops
    ctl = bridge.BridgeController(api, stall_sec=1, sleep=sleep)

    with pytest.raises(KeyboardInterrupt):
        ctl.run()

    assert api.events[:2] == ["build", "start"]
    assert api.events.count("teardown") == 0
    assert api.events.count("build") == 1


def test_rebuilds_after_stall():
    """Device stops feeding → watchdog stalls → teardown + fresh build+start."""
    api = FakeBridgeApi(data_flowing=False)
    ctl = bridge.BridgeController(api, stall_sec=0, sleep=RecordingSleep())

    ctl.run(max_stalls=1)

    assert api.events[:2] == ["build", "start"]          # initial connect
    assert "teardown" in api.events                       # device released
    # teardown → build → start ordering (release BEFORE a new source, so
    # the rebuild never hits "device in use")
    assert api.events.index("teardown") < api.events.index("build", api.events.index("teardown"))
    assert api.events.count("build") == 2                 # initial + rebuilt


def test_rebuild_retries_with_backoff():
    """Rebuild fails (device still gone / in use) → retry with backoff,
    doubling until the pipeline comes back."""
    api = FakeBridgeApi(data_flowing=False, reconnect_failures=2)
    sleep = RecordingSleep()
    ctl = bridge.BridgeController(api, stall_sec=0, sleep=sleep)

    ctl.run(max_stalls=1)

    assert api.events.count("build") == 4        # initial + 2 failures + success
    assert api.events.count("start") == 2        # initial + reconnected
    assert api.events.count("teardown") == 1
    backoffs = [s for s in sleep.slept if s >= 1.0]   # exclude the 0.5 poll sleeps
    assert 1.0 in backoffs and 2.0 in backoffs         # exponential growth


def test_reconnect_resets_backoff_after_success():
    """After a successful rebuild the backoff resets to initial — the next
    cycle's failure sleeps 1.0 again, never the grown 2.0."""
    api = FakeBridgeApi(data_flowing=False, reconnect_failures=1)
    sleep = RecordingSleep()
    ctl = bridge.BridgeController(api, stall_sec=0, sleep=sleep)

    ctl.run(max_stalls=2)   # two stall→rebuild cycles, each failing once

    assert ctl._backoff == ctl._backoff_initial
    # both cycles slept exactly 1.0 (reset), and no grown 2.0 ever appeared
    assert sleep.slept.count(1.0) == 2
    assert 2.0 not in sleep.slept


def test_bridge_importable_without_sdk():
    """The module must import with no gpype/pylsl (macOS) — top-level only
    stdlib. The SDK classes are defined but never touched."""
    assert hasattr(bridge, "GpypeBridge")
    assert hasattr(bridge, "DataWatchdog")
    assert hasattr(bridge, "LslWatchdogProbe")
