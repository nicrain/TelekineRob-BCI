"""P10④ + P12: gpype bridge data-flow watchdog + pipeline rebuild.

The pure logic (DataWatchdog stall detection, LslWatchdogProbe candidate
scan, BridgeController rebuild/retry/grace) lives in gpype_lsl_bridge.py and
imports gpype/pylsl lazily, so it runs here on macOS with a fake api — no
SDK, no real device.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtec_bridge"))
import gpype_lsl_bridge as bridge


class FakeBridgeApi:
    """Mimics GpypeBridge's surface: build/start/teardown/data_arrived.

    ``reconnect_failures`` makes the first N builds of EACH rebuild cycle
    fail (per-teardown cycle, like the real device still being gone/in use).
    ``flow_stops_after`` makes data_arrived return True for the first N calls
    of a cycle then False — the "device was healthy then dropped" shape; the
    flow counter resets on teardown (the device "comes back" after a rebuild
    cycle, mirroring the real P12 self-recovery).
    """

    def __init__(self, data_flowing: bool = True, reconnect_failures: int = 0,
                 flow_stops_after: int | None = None):
        self.events: list[str] = []          # call order, e.g. build→start
        self.data_flowing = data_flowing
        self.reconnect_failures = reconnect_failures
        self.flow_stops_after = flow_stops_after
        self._seen_teardown = False
        self._cycle_builds = 0
        self._flow_calls = 0

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
        self._flow_calls = 0  # device "comes back" after a rebuild cycle

    def data_arrived(self) -> bool:
        self.events.append("data")
        self._flow_calls += 1
        if self.flow_stops_after is not None and self._flow_calls > self.flow_stops_after:
            return False
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


class _Clock:
    """Test clock: time.monotonic stand-in the controller can advance."""
    def __init__(self, start: float = 0.0):
        self.t = start
    def __call__(self) -> float:
        return self.t
    def advance(self, secs: float) -> None:
        self.t += secs


# --- DataWatchdog (pure) ------------------------------------------------

def test_watchdog_stalls_after_inactivity_and_resets():
    t = [0.0]
    wd = bridge.DataWatchdog(stall_sec=5, now_fn=lambda: t[0])
    wd.mark_data()  # P12③: stall is only judged after data was seen

    assert wd.stalled() is False        # just marked
    t[0] = 4.9
    assert wd.stalled() is False
    t[0] = 5.0
    assert wd.stalled() is True         # no data for >= 5s
    wd.mark_data()
    assert wd.stalled() is False        # a sample resets the clock
    t[0] = 9.9
    assert wd.stalled() is False


def test_watchdog_never_stalls_before_data_seen():
    """P12③: a pipeline that never produced a sample is never torn down —
    even with a zero stall threshold and a huge gap."""
    t = [0.0]
    wd = bridge.DataWatchdog(stall_sec=0, now_fn=lambda: t[0])

    t[0] = 1000.0
    assert wd.stalled() is False


def test_watchdog_reset_forgets_seen_data():
    """P12③: after a rebuild the watchdog is per-instance — the new pipeline
    must produce a sample before a stall can be judged again."""
    t = [0.0]
    wd = bridge.DataWatchdog(stall_sec=0, now_fn=lambda: t[0])
    wd.mark_data()
    assert wd.stalled() is True

    wd.reset()
    assert wd.stalled() is False


def test_stall_sec_default_is_10s():
    """P12④: STALL_SEC raised to tolerate normal gaps between samples."""
    assert bridge.STALL_SEC >= 10.0


# --- LslWatchdogProbe (pylsl mocked) ------------------------------------

class _FakeStream:
    def __init__(self, name="gtec_bci_core4"):
        self.name = name


class _FakeInlet:
    """Returns samples while alive; `samples_until_dead` models a device that
    drops after N samples (the P12 residual-outlet / dead-outlet case)."""
    def __init__(self, alive: bool, samples_until_dead: int | None = None):
        self.alive = alive
        self._remaining = samples_until_dead

    def pull_sample(self, timeout=None):
        if self.alive and (self._remaining is None or self._remaining > 0):
            if self._remaining is not None:
                self._remaining -= 1
            return ([1.0], 0.0)
        return None


class _FakePylsl:
    """resolve_byprop returns the candidates in order; StreamInlet maps a
    stream object back to its inlet."""
    def __init__(self, candidates):
        self._candidates = candidates  # list of (stream, _FakeInlet)
        self.resolve_calls = 0

    def resolve_byprop(self, prop, value, timeout=None):
        self.resolve_calls += 1
        return [s for s, _ in self._candidates]

    def StreamInlet(self, stream, **kw):
        for s, inlet in self._candidates:
            if s is stream:
                return inlet
        raise ValueError("unknown stream")


def test_probe_picks_alive_outlet_among_residual(monkeypatch):
    """P12②: rapid rebuilds leave several same-name outlets — the probe must
    not lock to streams[0] (which may be a stale empty one); it scans and
    keeps the outlet that actually yields a sample."""
    stale = _FakeStream()
    alive = _FakeStream()
    pylsl = _FakePylsl([(stale, _FakeInlet(False)), (alive, _FakeInlet(True))])
    monkeypatch.setitem(sys.modules, "pylsl", pylsl)

    probe = bridge.LslWatchdogProbe()

    assert probe.data_arrived() is True  # scan found the alive candidate


def test_probe_re_resolves_after_persistent_empty(monkeypatch):
    """P12②: an inlet that goes empty (device dropped) is dropped after
    EMPTY_RESOLVE_AFTER reads and re-resolved — never locked to forever."""
    stale = _FakeStream()
    alive = _FakeStream()
    pylsl = _FakePylsl([(alive, _FakeInlet(True, samples_until_dead=1))])
    monkeypatch.setitem(sys.modules, "pylsl", pylsl)

    probe = bridge.LslWatchdogProbe(empty_resolve_after=3)

    assert probe.data_arrived() is True   # scan confirmed the alive outlet
    assert probe.data_arrived() is False  # outlet is now dead → empty reads
    assert probe.data_arrived() is False
    assert probe.data_arrived() is False  # 3rd empty → drop the inlet
    assert probe._inlet is None
    assert probe.data_arrived() is False  # re-resolve → nothing alive
    assert pylsl.resolve_calls >= 2       # it actually re-resolved


def test_probe_resolve_failure_is_not_alive(monkeypatch):
    pylsl = _FakePylsl([])
    monkeypatch.setitem(sys.modules, "pylsl", pylsl)
    assert bridge.LslWatchdogProbe().data_arrived() is False


# --- BridgeController: rebuild trigger ----------------------------------

def test_no_rebuild_while_data_flows():
    """Samples keep arriving → watchdog stays fresh → zero rebuilds."""
    api = FakeBridgeApi(data_flowing=True)
    sleep = RecordingSleep(calls_before_stop=3)  # stop after 3 poll loops
    ctl = bridge.BridgeController(api, stall_sec=1, grace_sec=0, sleep=sleep)

    with pytest.raises(KeyboardInterrupt):
        ctl.run()

    assert api.events[:2] == ["build", "start"]
    assert api.events.count("teardown") == 0
    assert api.events.count("build") == 1


def test_grace_blocks_stall_until_expired():
    """P12①: no rebuild while within grace_sec after (re)build — a pipeline
    is not torn down during outlet discovery. Here stall_sec=0 would stall
    instantly, but grace=10 keeps it alive."""
    clock = _Clock()
    api = FakeBridgeApi(flow_stops_after=1)  # data once, then dead
    def sleep(_secs):
        clock.advance(0.5)
        if clock.t >= 3.0:  # 6 loops
            raise KeyboardInterrupt
    ctl = bridge.BridgeController(api, stall_sec=0, grace_sec=10, sleep=sleep, now_fn=clock)

    with pytest.raises(KeyboardInterrupt):
        ctl.run()

    assert api.events.count("teardown") == 0
    assert api.events.count("build") == 1


def test_rebuilds_after_stall():
    """Device stops feeding after a healthy period → stall → teardown +
    fresh build+start."""
    api = FakeBridgeApi(flow_stops_after=1)  # data once, then dead
    ctl = bridge.BridgeController(api, stall_sec=0, grace_sec=0, sleep=RecordingSleep())

    ctl.run(max_stalls=1)

    assert api.events[:2] == ["build", "start"]          # initial connect
    assert "teardown" in api.events                       # device released
    assert api.events.index("teardown") < api.events.index("build", api.events.index("teardown"))
    assert api.events.count("build") == 2                 # initial + rebuilt


def test_rebuild_retries_with_backoff():
    """Rebuild fails (device still gone / in use) → retry with backoff,
    doubling until the pipeline comes back."""
    api = FakeBridgeApi(flow_stops_after=1, reconnect_failures=2)
    sleep = RecordingSleep()
    ctl = bridge.BridgeController(api, stall_sec=0, grace_sec=0, sleep=sleep)

    ctl.run(max_stalls=1)

    assert api.events.count("build") == 4        # initial + 2 failures + success
    assert api.events.count("start") == 2        # initial + reconnected
    assert api.events.count("teardown") == 1
    backoffs = [s for s in sleep.slept if s >= 1.0]   # exclude the 0.5 poll sleeps
    assert 1.0 in backoffs and 2.0 in backoffs         # exponential growth


def test_reconnect_resets_backoff_after_success():
    """After a successful rebuild the backoff resets to initial — the next
    cycle's failure sleeps 1.0 again, never the grown 2.0."""
    api = FakeBridgeApi(flow_stops_after=1, reconnect_failures=1)
    sleep = RecordingSleep()
    ctl = bridge.BridgeController(api, stall_sec=0, grace_sec=0, sleep=sleep)

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
