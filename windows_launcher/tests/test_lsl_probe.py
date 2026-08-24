"""P11 + P13: lsl_probe three-state liveness with sample freshness — pylsl
mocked, no real stream.

The probe runs under the device's python_cmd on Windows; here we feed it a
fake pylsl and assert the alive / stalled / not-found decision, including the
false-green case (stream resolves but yields no / only STALE samples).
"""
import builtins
import sys

import lsl_probe

NOW = 1000.0  # the fake clock


class _FakeInlet:
    def __init__(self, sample, timestamp):
        self._sample = sample
        self._timestamp = timestamp

    def pull_sample(self, timeout=None):
        if self._sample is None:
            return None
        return (self._sample, self._timestamp)


class _FakePylsl:
    def __init__(self, streams, sample, timestamp, now=NOW):
        self._streams = streams
        self._sample = sample
        self._timestamp = timestamp
        self._now = now

    def resolve_byprop(self, prop, value, timeout=None):
        return self._streams

    def StreamInlet(self, stream, **kw):
        return _FakeInlet(self._sample, self._timestamp)

    def local_clock(self):
        return self._now


def _patch_pylsl(monkeypatch, streams, sample, timestamp, now=NOW):
    monkeypatch.setitem(sys.modules, "pylsl", _FakePylsl(streams, sample, timestamp, now))


def test_probe_alive_when_fresh_sample(monkeypatch):
    """A FRESH sample (within freshness_sec of local_clock) → genuinely
    streaming → alive."""
    _patch_pylsl(monkeypatch, streams=[object()], sample=[1.0], timestamp=NOW - 0.5)
    assert lsl_probe.probe("gtec_bci_core4") == "alive"


def test_probe_stalled_when_sample_stale(monkeypatch):
    """P13 root cause: the outlet cached samples from before a power-off —
    an OLD sample must not count as alive."""
    _patch_pylsl(monkeypatch, streams=[object()], sample=[1.0], timestamp=NOW - 100.0)
    assert lsl_probe.probe("gtec_bci_core4") == "stalled"


def test_probe_stalled_when_stream_but_no_sample(monkeypatch):
    """P11: stream resolves but no sample → stalled, never alive."""
    _patch_pylsl(monkeypatch, streams=[object()], sample=None, timestamp=NOW)
    assert lsl_probe.probe("gtec_bci_core4") == "stalled"


def test_probe_not_found_when_no_stream(monkeypatch):
    """Bridge not running at all → nothing resolves → not-found."""
    _patch_pylsl(monkeypatch, streams=[], sample=None, timestamp=NOW)
    assert lsl_probe.probe("gtec_bci_core4") == "not-found"


def test_probe_stalled_when_pull_sample_raises(monkeypatch):
    """A pull that raises (e.g. inlet errors) is treated as stalled — safe."""
    class _BrokenInlet:
        def pull_sample(self, timeout=None):
            raise RuntimeError("inlet lost")

    class _Pylsl(_FakePylsl):
        def StreamInlet(self, stream, **kw):
            return _BrokenInlet()

    monkeypatch.setitem(sys.modules, "pylsl", _Pylsl([object()], None, NOW))
    assert lsl_probe.probe("gtec_bci_core4") == "stalled"


def test_probe_not_found_when_resolve_raises(monkeypatch):
    class _Raising(_FakePylsl):
        def resolve_byprop(self, prop, value, timeout=None):
            raise RuntimeError("LSL service down")

    monkeypatch.setitem(sys.modules, "pylsl", _Raising([], None, NOW))
    assert lsl_probe.probe("gtec_bci_core4") == "not-found"


def test_probe_no_pylsl(monkeypatch):
    """pylsl missing under the probe's python → no-pylsl (no crash)."""
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pylsl" or name.startswith("pylsl."):
            raise ImportError("pylsl not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert lsl_probe.probe("gtec_bci_core4") == "no-pylsl"
