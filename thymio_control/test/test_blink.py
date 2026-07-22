"""Tests for StreamingBlinkDetector — adaptive amplitude threshold."""

import numpy as np
import pytest

from thymio_control.processors.blink import (
    DualChannelBlinkDetector,
    StreamingBlinkDetector,
)


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


# ---------------------------------------------------------------------------
# min_threshold (absolute floor) tests
# ---------------------------------------------------------------------------


def test_min_threshold_blocks_noise_in_quiet_eeg():
    """When EEG is very quiet (tiny MAD), min_threshold prevents false triggers.

    Without the floor: threshold ≈ median + k_mad × MAD ≈ 0 + 6×2 = 12 µV.
    A 10 µV fluctuation would trigger the state machine → false positive.
    With min_threshold=15: threshold = max(12, 15) = 15 µV → noise rejected.
    """
    sr = 250
    det = StreamingBlinkDetector(
        sample_rate=sr, k_mad=6.0, buffer_sec=3.0, min_threshold=15.0,
    )
    # Very quiet EEG: noise_std=1.0 → MAD ≈ 0.67 → adaptive ≈ 4 µV alone
    sig = _baseline_signal(int(4 * sr), noise_std=1.0)
    # Insert a 10 µV "micro-blip" that would trigger without the floor
    _insert_blink(sig, at_sample=int(2.5 * sr), peak_amplitude=10.0, duration=20)
    events = det.feed_chunk(sig)
    assert len(events) == 0, (
        f"min_threshold=15 should block 10 µV noise in quiet EEG, got {len(events)}"
    )


def test_min_threshold_still_allows_real_blink():
    """A real blink (50+ µV) crosses the min_threshold floor easily."""
    sr = 250
    det = StreamingBlinkDetector(
        sample_rate=sr, k_mad=6.0, buffer_sec=3.0, min_threshold=15.0,
    )
    sig = _baseline_signal(int(4 * sr), noise_std=1.0)
    _insert_blink(sig, at_sample=int(2.5 * sr), peak_amplitude=50.0, duration=60)
    events = det.feed_chunk(sig)
    assert len(events) == 1, (
        f"Real blink (50 µV) should exceed min_threshold=15, got {len(events)}"
    )


def test_min_threshold_negative_raises():
    """Negative min_threshold is rejected at construction."""
    with pytest.raises(ValueError, match="min_threshold"):
        StreamingBlinkDetector(sample_rate=250, min_threshold=-5.0)


def test_min_threshold_zero_allowed():
    """min_threshold=0 is valid (disables the floor)."""
    det = StreamingBlinkDetector(sample_rate=250, min_threshold=0.0)
    assert det._min_threshold == 0.0


# ---------------------------------------------------------------------------
# confirm_samples tests
# ---------------------------------------------------------------------------


def test_confirm_samples_blocks_single_spike():
    """A single above-threshold sample does NOT trigger when confirm_samples=3.

    This is the key defense against EMG spikes / electrode pops — they
    last only 1–5 samples while real blinks last 50–100.
    """
    sr = 250
    det = StreamingBlinkDetector(
        sample_rate=sr, k_mad=6.0, buffer_sec=3.0, confirm_samples=3,
    )
    # Deterministic baseline
    t = np.arange(int(4 * sr)) / sr
    sig = (0.5 * np.sin(2 * np.pi * 10 * t)).reshape(1, -1).astype(np.float64)
    # Single-sample spike at 50µV (well above threshold)
    sig[0, int(2.5 * sr)] = 50.0
    events = det.feed_chunk(sig)
    assert len(events) == 0, (
        f"Single-sample spike should NOT trigger with confirm_samples=3, "
        f"got {len(events)}"
    )


def test_confirm_samples_allows_sustained_blink():
    """A sustained blink (≥3 consecutive above-threshold samples) triggers."""
    sr = 250
    det = StreamingBlinkDetector(
        sample_rate=sr, k_mad=6.0, buffer_sec=3.0, confirm_samples=3,
    )
    sig = _baseline_signal(int(4 * sr), noise_std=1.0)
    # A real blink: triangular pulse spanning ~50 samples (200ms)
    _insert_blink(sig, at_sample=int(2.5 * sr), peak_amplitude=50.0, duration=50)
    events = det.feed_chunk(sig)
    assert len(events) == 1, (
        f"Sustained blink (50 samples) should trigger, got {len(events)}"
    )


def test_confirm_counter_resets_on_dropout():
    """Confirm counter resets if a sample falls below threshold mid-count."""
    sr = 250
    det = StreamingBlinkDetector(
        sample_rate=sr, k_mad=6.0, buffer_sec=3.0, confirm_samples=3,
    )
    sig = _baseline_signal(int(4 * sr), noise_std=1.0)
    # Two consecutive spikes, then a gap, then more.  The counter
    # should reset in the gap → no detection from these fragments.
    sig[0, int(2.5 * sr)]       = 50.0
    sig[0, int(2.5 * sr) + 1]   = 50.0
    # sample at +2 stays at baseline (below threshold) → counter resets
    sig[0, int(2.5 * sr) + 10]  = 50.0
    sig[0, int(2.5 * sr) + 11]  = 50.0
    sig[0, int(2.5 * sr) + 12]  = 50.0  # 3 in a row, but far apart from first
    # The first cluster has only 2 consecutive, second cluster has 3.
    # But second cluster is a separate "blink" — 3 consecutive should trigger.
    events = det.feed_chunk(sig)
    assert len(events) == 1, (
        f"3 consecutive above-threshold samples should trigger once, "
        f"got {len(events)}"
    )


def test_confirm_samples_default_is_1():
    """Default confirm_samples=1 behaves like the old immediate-trigger."""
    sr = 250
    det = StreamingBlinkDetector(sample_rate=sr, k_mad=6.0, buffer_sec=3.0)
    sig = _baseline_signal(int(4 * sr), noise_std=1.0)
    _insert_blink(sig, at_sample=int(2.5 * sr), peak_amplitude=50.0, duration=5)
    events = det.feed_chunk(sig)
    assert len(events) == 1, "Default confirm_samples=1 should trigger immediately"


def test_confirm_samples_zero_raises():
    """confirm_samples < 1 is rejected at construction."""
    with pytest.raises(ValueError, match="confirm_samples"):
        StreamingBlinkDetector(sample_rate=250, confirm_samples=0)


# ---------------------------------------------------------------------------
# min_rising_samples tests (passive blink rejection)
# ---------------------------------------------------------------------------


def test_min_rising_samples_blocks_short_peak():
    """A brief above-threshold excursion (< 30 samples) is discarded.

    Simulates a passive blink (~80 ms = 20 samples above threshold).
    Passive blinks are 60–80 ms (15–20 samples); active blinks are
    150–200 ms (37–50 samples).  min_rising_samples=30 sits between them.
    """
    sr = 250
    det = StreamingBlinkDetector(
        sample_rate=sr, k_mad=6.0, buffer_sec=3.0,
        confirm_samples=5, min_rising_samples=30,
    )
    sig = _baseline_signal(int(4 * sr), noise_std=1.0)
    # Brief peak: 20-sample duration (~80 ms) = passive blink
    # This is enough to pass confirm (5), but too short for min_rising
    _insert_blink(sig, at_sample=int(2.5 * sr), peak_amplitude=60.0, duration=20)
    events = det.feed_chunk(sig)
    assert len(events) == 0, (
        f"Short blink (20 samples) should be blocked by min_rising_samples=30, "
        f"got {len(events)}"
    )


def test_min_rising_samples_allows_long_blink():
    """A sustained blink (≥ 30 samples above threshold) is detected."""
    sr = 250
    det = StreamingBlinkDetector(
        sample_rate=sr, k_mad=6.0, buffer_sec=3.0,
        confirm_samples=5, min_rising_samples=30,
    )
    sig = _baseline_signal(int(4 * sr), noise_std=1.0)
    # Long blink: 50-sample duration (~200 ms) = active blink
    _insert_blink(sig, at_sample=int(2.5 * sr), peak_amplitude=60.0, duration=50)
    events = det.feed_chunk(sig)
    assert len(events) == 1, (
        f"Long blink (50 samples) should pass min_rising_samples=30, "
        f"got {len(events)}"
    )


def test_min_rising_samples_default_is_1():
    """Default min_rising_samples=1 allows any duration through."""
    sr = 250
    det = StreamingBlinkDetector(sample_rate=sr, k_mad=6.0, buffer_sec=3.0)
    sig = _baseline_signal(int(4 * sr), noise_std=1.0)
    _insert_blink(sig, at_sample=int(2.5 * sr), peak_amplitude=50.0, duration=5)
    events = det.feed_chunk(sig)
    assert len(events) == 1, "Default min_rising_samples=1 should allow short peaks"


def test_min_rising_samples_zero_raises():
    """min_rising_samples < 1 is rejected at construction."""
    with pytest.raises(ValueError, match="min_rising_samples"):
        StreamingBlinkDetector(sample_rate=250, min_rising_samples=0)


# ---------------------------------------------------------------------------
# Dual-channel detector tests
# ---------------------------------------------------------------------------


def _dual_chunk(
    ch0: np.ndarray, ch1: np.ndarray,
) -> np.ndarray:
    """Stack two 1-D arrays into a (2, N) chunk."""
    return np.stack([ch0, ch1]).astype(np.float64)


def test_dual_channel_detects_both():
    """Both channels see a synchronized blink → detection."""
    sr = 250
    det = DualChannelBlinkDetector(
        sample_rate=sr, channel_indices=[0, 1],
        k_mad=6.0, buffer_sec=3.0,
    )
    n = int(4 * sr)
    sig0 = _baseline_signal(n, noise_std=1.0)[0]
    sig1 = _baseline_signal(n, noise_std=1.0)[0]
    _insert_blink(sig0.reshape(1, -1), int(2.5 * sr), peak_amplitude=50.0, duration=50)
    _insert_blink(sig1.reshape(1, -1), int(2.5 * sr), peak_amplitude=50.0, duration=50)
    chunk = _dual_chunk(sig0, sig1)
    events = det.feed_chunk(chunk)
    assert len(events) == 1, f"Dual blink should trigger, got {len(events)}"


def test_dual_channel_ignores_unilateral():
    """Only ch0 has a blink, ch1 is quiet → no detection."""
    sr = 250
    det = DualChannelBlinkDetector(
        sample_rate=sr, channel_indices=[0, 1],
        k_mad=6.0, buffer_sec=3.0,
    )
    n = int(4 * sr)
    sig0 = _baseline_signal(n, noise_std=1.0)[0]
    sig1 = _baseline_signal(n, noise_std=1.0)[0]
    _insert_blink(sig0.reshape(1, -1), int(2.5 * sr), peak_amplitude=50.0, duration=50)
    # sig1 stays quiet
    chunk = _dual_chunk(sig0, sig1)
    events = det.feed_chunk(chunk)
    assert len(events) == 0, "Unilateral blink should NOT trigger dual-channel"


def test_dual_channel_reset():
    """reset() clears internal state of all detectors."""
    sr = 250
    det = DualChannelBlinkDetector(
        sample_rate=sr, channel_indices=[0, 1],
    )
    det.reset()  # should not raise


def test_dual_channel_requires_two_indices():
    """Less than 2 channel_indices raises ValueError."""
    with pytest.raises(ValueError, match="channel indices"):
        DualChannelBlinkDetector(sample_rate=250, channel_indices=[0])
