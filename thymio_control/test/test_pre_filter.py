"""Tests for StreamingPreFilter — IIR bandpass + notch in streaming mode.

Filter chain: 4th-order Butterworth bandpass [0.5–45] Hz
           → 4th-order Butterworth bandstop [48–52] Hz (notch)

Zero initial conditions → transient lasts ~1–2 s (0.5 Hz HP pole).
All steady-state assertions skip the first 1.5 s to stay in the
settled region.
"""

import numpy as np
import pytest

from thymio_control.processors.band_power import StreamingPreFilter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SETTLE_S = 1.5  # seconds to skip for steady-state assertions


def _rms(signal: np.ndarray) -> float:
    return float(np.sqrt(np.mean(signal.astype(np.float64) ** 2)))


def _tone(
    freq: float,
    duration: float,
    sample_rate: int,
    amplitude: float = 1.0,
) -> np.ndarray:
    """Generate a pure sine tone."""
    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    return amplitude * np.sin(2 * np.pi * freq * t)


def _attenuation_db(input_rms: float, output_rms: float) -> float:
    """Attenuation in dB (positive = reduction)."""
    if output_rms < 1e-15:
        return 100.0  # effectively infinite
    return float(20 * np.log10(input_rms / output_rms))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dc_removed():
    """DC offset is attenuated by the 0.5 Hz high-pass (settled region)."""
    sr, n_ch = 250, 1
    f = StreamingPreFilter(sample_rate=sr, n_channels=n_ch)

    # 4-second signal: DC = 100, no AC
    chunk = np.full((n_ch, int(4 * sr)), 100.0, dtype=np.float64)
    f.apply(chunk)
    skip = int(SETTLE_S * sr)
    steady = chunk[:, skip:]

    rms_val = _rms(steady)
    assert rms_val < 1.0, f"DC not removed: RMS={rms_val:.1f}"


def test_notch_50hz():
    """50 Hz (mains hum) is attenuated by >30 dB (settled region)."""
    sr, n_ch = 250, 1
    f = StreamingPreFilter(sample_rate=sr, n_channels=n_ch)

    # 3-second 50 Hz tone
    chunk = _tone(50, 3.0, sr).reshape(n_ch, -1)
    in_rms = _rms(chunk)
    f.apply(chunk)
    skip = int(SETTLE_S * sr)
    out_rms = _rms(chunk[:, skip:])

    att = _attenuation_db(in_rms, out_rms)
    assert att > 30, f"50 Hz attenuation only {att:.1f} dB, expected >30 dB"


def test_10hz_preserved():
    """10 Hz (alpha band) passes through the bandpass nearly intact."""
    sr, n_ch = 250, 1
    f = StreamingPreFilter(sample_rate=sr, n_channels=n_ch)

    chunk = _tone(10, 3.0, sr).reshape(n_ch, -1)
    skip = int(SETTLE_S * sr)
    in_rms = _rms(chunk[:, skip:])
    f.apply(chunk)
    out_rms = _rms(chunk[:, skip:])

    att = _attenuation_db(in_rms, out_rms)
    assert att < 1.0, f"10 Hz attenuated by {att:.2f} dB, should be <1 dB"


def test_streaming_continuity():
    """Two consecutive chunks produce the same result as one merged chunk."""
    sr, n_ch = 250, 1
    np.random.seed(42)
    signal = np.random.randn(int(2.5 * sr)).astype(np.float64)  # 2.5 s of noise

    # One-shot
    f1 = StreamingPreFilter(sample_rate=sr, n_channels=n_ch)
    merged = signal.reshape(n_ch, -1).copy()
    f1.apply(merged)

    # Two chunks
    f2 = StreamingPreFilter(sample_rate=sr, n_channels=n_ch)
    split = int(1.0 * sr)
    a = signal[:split].reshape(n_ch, -1).copy()
    b = signal[split:].reshape(n_ch, -1).copy()
    f2.apply(a)
    f2.apply(b)
    two_step = np.concatenate([a, b], axis=1)

    # Compare last 250 samples (after transients settle)
    np.testing.assert_allclose(
        merged[:, -250:], two_step[:, -250:],
        rtol=1e-5, atol=1e-8,
    )


def test_multi_channel():
    """Each channel is filtered independently."""
    sr, n_ch = 250, 2
    f = StreamingPreFilter(sample_rate=sr, n_channels=n_ch)

    # Channel 0: DC offset, channel 1: 10 Hz tone
    duration = 4.0
    t = np.arange(int(duration * sr)) / sr
    chunk = np.zeros((n_ch, len(t)), dtype=np.float64)
    chunk[0, :] = 50.0  # DC
    chunk[1, :] = np.sin(2 * np.pi * 10 * t)

    f.apply(chunk)
    skip = int(SETTLE_S * sr)

    # Channel 0 DC should be removed
    assert _rms(chunk[0, skip:]) < 1.0
    # Channel 1 alpha should survive
    att_ch1 = _attenuation_db(1.0 / np.sqrt(2), _rms(chunk[1, skip:]))
    assert att_ch1 < 1.5, f"ch1 10 Hz attenuated by {att_ch1:.2f} dB"


def test_reset_clears_state():
    """After reset, the filter behaves identically to a fresh instance."""
    sr, n_ch = 250, 1
    np.random.seed(7)
    signal = np.random.randn(int(1.0 * sr)).astype(np.float64).reshape(n_ch, -1)

    # Fresh
    f1 = StreamingPreFilter(sample_rate=sr, n_channels=n_ch)
    chunk1 = signal.copy()
    f1.apply(chunk1)

    # Used then reset
    f2 = StreamingPreFilter(sample_rate=sr, n_channels=n_ch)
    # Feed some garbage first
    garbage = np.random.randn(1, 100).astype(np.float64)
    f2.apply(garbage)
    f2.reset()
    # Now should behave like fresh
    chunk2 = signal.copy()
    f2.apply(chunk2)

    np.testing.assert_allclose(chunk1, chunk2, rtol=1e-12, atol=1e-12)
