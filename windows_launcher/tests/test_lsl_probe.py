"""P11: lsl_probe three-state liveness — pylsl mocked, no real stream.

The probe runs under the device's python_cmd on Windows; here we feed it a
fake pylsl and assert the alive / stalled / not-found decision, including
the false-green case (stream resolves but yields no sample).
"""
import builtins
import sys

import lsl_probe


class _FakeInlet:
    def __init__(self, sample):
        self._sample = sample

    def pull_sample(self, timeout=None):
        return self._sample


class _FakePylsl:
    def __init__(self, streams, sample):
        self._streams = streams
        self._sample = sample

    def resolve_byprop(self, prop, value, timeout=None):
        return self._streams

    def StreamInlet(self, stream, **kw):
        return _FakeInlet(self._sample)


def _patch_pylsl(monkeypatch, streams, sample):
    monkeypatch.setitem(sys.modules, "pylsl", _FakePylsl(streams, sample))


def test_probe_alive_when_stream_yields_sample(monkeypatch):
    """Stream resolved AND a sample arrived → genuinely streaming."""
    _patch_pylsl(monkeypatch, streams=[object()], sample=([1.0], 0.0))
    assert lsl_probe.probe("gtec_bci_core4") == "alive"


def test_probe_stalled_when_stream_but_no_sample(monkeypatch):
    """P11 root cause: bridge still publishes the stream while the device is
    off → resolve succeeds but no sample → stalled, never alive."""
    _patch_pylsl(monkeypatch, streams=[object()], sample=None)
    assert lsl_probe.probe("gtec_bci_core4") == "stalled"


def test_probe_not_found_when_no_stream(monkeypatch):
    """Bridge not running at all → nothing resolves → not-found."""
    _patch_pylsl(monkeypatch, streams=[], sample=None)
    assert lsl_probe.probe("gtec_bci_core4") == "not-found"


def test_probe_stalled_when_pull_sample_raises(monkeypatch):
    """A pull that raises (e.g. inlet errors) is treated as stalled — safe."""
    class _BrokenInlet:
        def pull_sample(self, timeout=None):
            raise RuntimeError("inlet lost")

    class _Pylsl(_FakePylsl):
        def StreamInlet(self, stream, **kw):
            return _BrokenInlet()

    monkeypatch.setitem(sys.modules, "pylsl", _Pylsl([object()], None))
    assert lsl_probe.probe("gtec_bci_core4") == "stalled"


def test_probe_not_found_when_resolve_raises(monkeypatch):
    class _Raising(_FakePylsl):
        def resolve_byprop(self, prop, value, timeout=None):
            raise RuntimeError("LSL service down")

    monkeypatch.setitem(sys.modules, "pylsl", _Raising([], None))
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
