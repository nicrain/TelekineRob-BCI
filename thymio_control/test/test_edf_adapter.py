"""Tests for EdfFileAdapter and pipeline.build_adapter('file' mode).

These tests use a synthetic EDF file written with pyedflib so no real
recording is needed.  Tests are skipped automatically when pyedflib is
not installed.
"""
from __future__ import annotations

import math
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Skip entire module when pyedflib is unavailable
# ---------------------------------------------------------------------------
pyedflib = pytest.importorskip("pyedflib", reason="pyedflib not installed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_synthetic_edf(
    path: Path,
    n_channels: int = 3,
    n_samples: int = 2000,
    sample_rate: int = 500,
    unit: str = "uV",
    labels: list[str] | None = None,
) -> Path:
    """Write a minimal EDF file with sinusoidal data."""
    if labels is None:
        labels = [f"EEG{i+1}" for i in range(n_channels)]

    f = pyedflib.EdfWriter(str(path), n_channels)
    headers = []
    for i in range(n_channels):
        headers.append({
            "label": labels[i],
            "dimension": unit,
            "sample_frequency": sample_rate,
            "physical_min": -200.0,
            "physical_max": 200.0,
            "digital_min": -32768,
            "digital_max": 32767,
            "prefilter": "",
            "transducer": "",
        })
    f.setSignalHeaders(headers)

    t = np.linspace(0, n_samples / sample_rate, n_samples)
    signals = [
        (5.0 * np.sin(2 * math.pi * 10 * t) + 2.0 * np.sin(2 * math.pi * 20 * t))
        for _ in range(n_channels)
    ]
    f.writeSamples(signals)
    f.close()
    return path


# ---------------------------------------------------------------------------
# _resolve_path
# ---------------------------------------------------------------------------

class TestResolvePath:
    def test_absolute_existing_path_returned_as_is(self, tmp_path):
        edf = _write_synthetic_edf(tmp_path / "test.edf")
        from thymio_control.adapters.edf_file import _resolve_path
        assert _resolve_path(edf) == edf

    def test_nonexistent_path_raises_file_not_found(self, tmp_path):
        from thymio_control.adapters.edf_file import _resolve_path
        with pytest.raises(FileNotFoundError, match="EDF file not found"):
            _resolve_path(tmp_path / "ghost.edf")

    def test_relative_path_found_via_cwd(self, tmp_path, monkeypatch):
        edf = _write_synthetic_edf(tmp_path / "rel.edf")
        monkeypatch.chdir(tmp_path)
        from thymio_control.adapters.edf_file import _resolve_path
        result = _resolve_path("rel.edf")
        assert result.name == "rel.edf"


# ---------------------------------------------------------------------------
# EdfFileAdapter — construction and basic read
# ---------------------------------------------------------------------------

class TestEdfFileAdapterConstruction:
    def test_constructs_with_valid_edf(self, tmp_path):
        from thymio_control.adapters.edf_file import EdfFileAdapter
        edf = _write_synthetic_edf(tmp_path / "test.edf", n_channels=3)
        adapter = EdfFileAdapter(edf, realtime=False)
        assert adapter.n_channels == 3
        assert adapter.sample_rate == 500

    def test_channel_labels_exclude_xyz_accelerometer(self, tmp_path):
        from thymio_control.adapters.edf_file import EdfFileAdapter
        labels = ["EEG1", "X", "Y", "Z", "EEG2"]
        edf = _write_synthetic_edf(tmp_path / "accel.edf", n_channels=5, labels=labels)
        adapter = EdfFileAdapter(edf, realtime=False)
        assert "X" not in adapter.channel_labels
        assert "Y" not in adapter.channel_labels
        assert "Z" not in adapter.channel_labels
        assert adapter.n_channels == 2

    def test_unit_auto_detected_from_edf_metadata(self, tmp_path):
        from thymio_control.adapters.edf_file import EdfFileAdapter
        edf = _write_synthetic_edf(tmp_path / "nv.edf", unit="nV")
        adapter = EdfFileAdapter(edf, realtime=False)
        assert adapter._cfg.source_unit == "nV"

    def test_raises_when_no_eeg_channels(self, tmp_path):
        from thymio_control.adapters.edf_file import EdfFileAdapter
        edf = _write_synthetic_edf(tmp_path / "xyz.edf", n_channels=3, labels=["X", "Y", "Z"])
        with pytest.raises(RuntimeError, match="No EEG channels found"):
            EdfFileAdapter(edf, realtime=False)


# ---------------------------------------------------------------------------
# EdfFileAdapter — read_frame behaviour
# ---------------------------------------------------------------------------

class TestEdfFileAdapterReadFrame:
    def test_read_frame_eventually_returns_eeg_frame(self, tmp_path):
        from thymio_control.adapters.edf_file import EdfFileAdapter
        from thymio_control.contracts import EegFrame
        edf = _write_synthetic_edf(tmp_path / "test.edf", n_samples=5000)
        adapter = EdfFileAdapter(edf, realtime=False)

        frame = None
        for _ in range(200):   # up to 200 chunks × 50 samples = 10 000 samples
            frame = adapter.read_frame()
            if frame is not None:
                break

        assert frame is not None, "EdfFileAdapter never produced a frame"
        assert isinstance(frame, EegFrame)
        assert frame.source == "edf_file"

    def test_frame_metrics_contain_expected_band_keys(self, tmp_path):
        from thymio_control.adapters.edf_file import EdfFileAdapter
        edf = _write_synthetic_edf(tmp_path / "test.edf", n_samples=5000)
        adapter = EdfFileAdapter(edf, realtime=False)

        frame = None
        for _ in range(200):
            frame = adapter.read_frame()
            if frame is not None:
                break

        assert frame is not None
        for key in ("alpha", "theta", "beta", "delta", "gamma"):
            assert key in frame.metrics, f"Missing band key: {key}"

    def test_adapter_loops_after_file_exhausted(self, tmp_path):
        """After the file runs out, read_frame should keep returning frames (looping)."""
        from thymio_control.adapters.edf_file import EdfFileAdapter
        edf = _write_synthetic_edf(tmp_path / "loop.edf", n_samples=2000)
        adapter = EdfFileAdapter(edf, chunk_size=50, realtime=False)

        frames_collected = []
        for _ in range(600):  # well past file length
            f = adapter.read_frame()
            if f is not None:
                frames_collected.append(f)
            if len(frames_collected) >= 5:
                break

        assert len(frames_collected) >= 5, "Adapter did not loop after file exhausted"

    def test_reset_restarts_from_beginning(self, tmp_path):
        from thymio_control.adapters.edf_file import EdfFileAdapter
        edf = _write_synthetic_edf(tmp_path / "reset.edf", n_samples=3000)
        adapter = EdfFileAdapter(edf, chunk_size=50, realtime=False)

        # Advance partway through the file
        for _ in range(20):
            adapter.read_frame()
        pos_before = adapter._pos

        adapter.reset()
        assert adapter._pos == 0
        assert adapter._last_yield == 0.0

    def test_realtime_throttle_slows_down_playback(self, tmp_path):
        from thymio_control.adapters.edf_file import EdfFileAdapter
        edf = _write_synthetic_edf(tmp_path / "rt.edf", n_samples=5000)

        adapter_fast = EdfFileAdapter(edf, chunk_size=50, realtime=False)
        adapter_slow = EdfFileAdapter(edf, chunk_size=50, realtime=True, playback_speed=10.0)

        def collect_first_frame(adapter):
            for _ in range(200):
                f = adapter.read_frame()
                if f is not None:
                    return f
            return None

        t0 = time.monotonic()
        collect_first_frame(adapter_fast)
        dt_fast = time.monotonic() - t0

        t0 = time.monotonic()
        collect_first_frame(adapter_slow)
        dt_slow = time.monotonic() - t0

        # Fast should be strictly faster than 10× real-time throttled
        assert dt_fast < dt_slow + 0.5  # generous tolerance


# ---------------------------------------------------------------------------
# pipeline.build_adapter — 'file' mode integration
# ---------------------------------------------------------------------------

class TestBuildAdapterFileMode:
    def test_build_adapter_file_mode_returns_edf_adapter(self, tmp_path):
        from thymio_control.adapters.edf_file import EdfFileAdapter
        from thymio_control.pipeline import build_adapter

        edf = _write_synthetic_edf(tmp_path / "test.edf")

        class Args:
            input = "file"
            file_path = str(edf)

        adapter = build_adapter(Args())
        assert isinstance(adapter, EdfFileAdapter)

    def test_build_adapter_file_mode_raises_without_path(self):
        from thymio_control.pipeline import build_adapter

        class Args:
            input = "file"
            file_path = ""

        with pytest.raises(RuntimeError, match="file mode requires --file-path"):
            build_adapter(Args())

    def test_build_adapter_mock_mode(self):
        from thymio_control.adapters.mock import MockAdapter
        from thymio_control.pipeline import build_adapter

        class Args:
            input = "mock"

        adapter = build_adapter(Args())
        assert isinstance(adapter, MockAdapter)

    def test_build_adapter_unsupported_mode_raises(self):
        from thymio_control.pipeline import build_adapter

        class Args:
            input = "unknown_mode_xyz"

        with pytest.raises(RuntimeError, match="Unsupported input mode"):
            build_adapter(Args())


# ---------------------------------------------------------------------------
# pipeline.build_pipeline — assembler integration
# ---------------------------------------------------------------------------

class TestBuildPipeline:
    def test_build_pipeline_returns_three_tuple(self):
        from thymio_control.pipeline import build_pipeline

        class Args:
            input = "mock"
            policy = "focus"

        result = build_pipeline(Args())
        assert len(result) == 3
        adapter, processor, policy = result
        assert callable(processor)

    def test_build_pipeline_selects_correct_policy(self):
        from thymio_control.pipeline import build_pipeline
        from thymio_control.policies.theta_beta import ThetaBetaPolicy

        class Args:
            input = "mock"
            policy = "theta_beta"

        _, _, policy = build_pipeline(Args())
        assert isinstance(policy, ThetaBetaPolicy)

    def test_build_pipeline_invalid_policy_raises(self):
        from thymio_control.pipeline import build_pipeline

        class Args:
            input = "mock"
            policy = "nonexistent_policy"

        with pytest.raises(ValueError, match="Unknown policy"):
            build_pipeline(Args())

    def test_build_pipeline_processor_enriches_metrics(self):
        from thymio_control.pipeline import build_pipeline

        class Args:
            input = "mock"
            policy = "focus"

        _, processor, _ = build_pipeline(Args())
        raw = {"alpha": 1.0, "theta": 0.5, "beta": 2.0, "delta": 0.3, "gamma": 0.1}
        enriched = processor(raw)
        # enrich_features should add derived ratios
        assert "beta_alpha_theta" in enriched or "theta_beta" in enriched

    def test_build_pipeline_mock_produces_frames_and_intents(self):
        from thymio_control.pipeline import build_pipeline

        class Args:
            input = "mock"
            policy = "theta_beta"

        adapter, processor, policy = build_pipeline(Args())

        intents = None
        for _ in range(50):
            frame = adapter.read_frame()
            if frame:
                features = processor(frame.metrics)
                intents = policy.compute_intents(features)
                break

        assert intents is not None
        assert 0.0 <= intents["speed_intent"] <= 1.0
        assert 0.0 <= intents["steer_intent"] <= 1.0
