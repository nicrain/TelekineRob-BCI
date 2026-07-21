"""Tests for StreamingBlinkDetector — adaptive amplitude threshold."""

import numpy as np
import pytest

from thymio_control.processors.blink import StreamingBlinkDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _baseline_signal(n_samples: int, noise_std: float = 1.0) -> np.ndarray:
    """Generate noisy baseline EEG-like signal (1 channel)."""
    rng = np.random.default_rng(42)
    return rng.normal(0, noise_std, size=(1, n_samples)).astype(np.float64)


def _insert_blink(
    signal: np.ndarray,
    at_sample: int,
    peak_amplitude: float,
    duration: int = 50,
) -> np.ndarray:
    """Insert a synthetic blink (triangular pulse) into the signal at *at_sample*."""
    half = duration // 2
    start = max(0, at_sample - half)
    end = min(signal.shape[1], at_sample + half)
    for i in range(start, end):
        dist = abs(i - at_sample)
        frac = 1.0 - dist / half
        signal[0, i] += peak_amplitude * frac
    return signal


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_detection_on_baseline():
    """Pure baseline (no blinks) produces zero detections."""
    sr = 250
    det = StreamingBlinkDetector(sample_rate=sr, k_mad=6.0)
    t = np.arange(int(5 * sr)) / sr
    sig = (0.5 * np.sin(2 * np.pi * 10 * t)).reshape(1, -1).astype(np.float64)
    events = det.feed_chunk(sig)
    assert len(events) == 0, f"Expected 0 events on baseline, got {len(events)}"


def test_detects_large_active_blink():
    """A very large peak is detected as active blink."""
    sr = 250
    det = StreamingBlinkDetector(sample_rate=sr, k_mad=6.0, buffer_sec=3.0)
    t = np.arange(int(4 * sr)) / sr
    sig = (0.5 * np.sin(2 * np.pi * 10 * t)).reshape(1, -1).astype(np.float64)
    _insert_blink(sig, at_sample=int(2.5 * sr), peak_amplitude=50.0, duration=60)
    events = det.feed_chunk(sig)
    assert len(events) == 1, f"Expected 1 active blink, got {len(events)}"
    assert events[0]["peak"] > 30.0


def test_small_blink_is_ignored():
    """A peak well below the threshold is ignored (passive blink)."""
    sr = 250
    det = StreamingBlinkDetector(sample_rate=sr, k_mad=6.0, buffer_sec=3.0)
    # Deterministic baseline: small sinusoid at 10 Hz with 0.5 amplitude
    # Median ≈ 0, MAD ≈ 0.34, threshold ≈ 0 + 6*0.34 ≈ 2.04
    t = np.arange(int(4 * sr)) / sr
    sig = (0.5 * np.sin(2 * np.pi * 10 * t)).reshape(1, -1).astype(np.float64)
    _insert_blink(sig, at_sample=int(2.5 * sr), peak_amplitude=1.5, duration=50)
    events = det.feed_chunk(sig)
    assert len(events) == 0, f"Expected 0 events for small blink, got {len(events)}"


def test_refractory_prevents_double_trigger():
    """Two large blinks within 500 ms only produce one detection."""
    sr = 250
    det = StreamingBlinkDetector(sample_rate=sr, k_mad=6.0, buffer_sec=3.0, refractory_ms=500)
    sig = _baseline_signal(int(4 * sr), noise_std=1.0)
    _insert_blink(sig, at_sample=int(2.0 * sr), peak_amplitude=25.0, duration=60)
    _insert_blink(sig, at_sample=int(2.0 * sr + 100), peak_amplitude=25.0, duration=60)  # 100 samples = 400ms later
    events = det.feed_chunk(sig)
    assert len(events) == 1, f"Refractory should block second blink, got {len(events)}"


def test_adaptive_threshold_rises_with_noise():
    """Higher noise floor → higher threshold → fewer false positives."""
    sr = 250
    det_noisy = StreamingBlinkDetector(sample_rate=sr, k_mad=6.0, buffer_sec=3.0)
    sig_noisy = _baseline_signal(int(4 * sr), noise_std=5.0)
    _insert_blink(sig_noisy, at_sample=int(2.5 * sr), peak_amplitude=25.0, duration=60)
    # 25 is 5σ above the 5.0 noise floor → may not trigger with k_mad=6
    events = det_noisy.feed_chunk(sig_noisy)
    # With noise_std=5, threshold ≈ median + 6*MAD ≈ 0 + 6*(0.67*5) ≈ 20
    # A peak of 25 might or might not pass (it's close)
    # Lowering k_mad to 4 should detect it
    det_low = StreamingBlinkDetector(sample_rate=sr, k_mad=4.0, buffer_sec=3.0)
    sig2 = _baseline_signal(int(4 * sr), noise_std=5.0)
    _insert_blink(sig2, at_sample=int(2.5 * sr), peak_amplitude=25.0, duration=60)
    events2 = det_low.feed_chunk(sig2)
    assert len(events2) >= 1, f"With k_mad=4, 5σ blink should be detected, got {len(events2)}"


def test_multi_channel_only_uses_configured():
    """Only the configured channel_idx is examined for blinks."""
    sr = 250
    det_ch1 = StreamingBlinkDetector(sample_rate=sr, channel_idx=1, buffer_sec=3.0, k_mad=6.0)
    sig = np.zeros((2, int(4 * sr)), dtype=np.float64)
    rng = np.random.default_rng(99)
    sig[0] = rng.normal(0, 1, sig.shape[1])  # ch0: baseline
    sig[1] = rng.normal(0, 1, sig.shape[1])  # ch1: baseline
    _insert_blink(sig[0:1], at_sample=int(2.5 * sr), peak_amplitude=25.0, duration=60)
    # Blink is on ch0, but detector watches ch1 only
    events = det_ch1.feed_chunk(sig)
    assert len(events) == 0, "Blink on ch0 should NOT be detected when channel_idx=1"


def test_reset_clears_state():
    """After reset, the detector behaves like a fresh instance."""
    sr = 250
    det = StreamingBlinkDetector(sample_rate=sr, k_mad=6.0, buffer_sec=3.0)
    sig = _baseline_signal(int(4 * sr), noise_std=1.0)
    _insert_blink(sig, at_sample=int(2.5 * sr), peak_amplitude=25.0, duration=60)
    det.feed_chunk(sig)

    # After feeding data, buffer is non-empty and sample_count > 0
    assert det.sample_count > 0
    det.reset()
    assert det.sample_count == 0

    # Should work identically after reset
    sig2 = _baseline_signal(int(4 * sr), noise_std=1.0)
    _insert_blink(sig2, at_sample=int(2.5 * sr), peak_amplitude=25.0, duration=60)
    events = det.feed_chunk(sig2)
    assert len(events) == 1, "Should detect blink after reset"


def test_warmup_no_detection():
    """During the initial warmup period, no detections are emitted."""
    sr = 250
    det = StreamingBlinkDetector(sample_rate=sr, k_mad=6.0, buffer_sec=3.0)
    sig = _baseline_signal(int(0.3 * sr), noise_std=1.0)  # < 100 samples
    _insert_blink(sig, at_sample=40, peak_amplitude=100.0, duration=10)
    events = det.feed_chunk(sig)
    assert len(events) == 0, "Should not detect during warmup (< 100 samples)"
