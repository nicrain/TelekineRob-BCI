"""Regression tests for DSP streaming + manual-Welch fixes."""

import numpy as np
import pytest

from thymio_control.processors.band_power import (
    DSPConfig,
    StreamingBandPowerExtractor,
    _manual_welch_psd,
)


# ---------------------------------------------------------------------------
# Fix 1 — hop > window must fail fast (feed_chunk used to hang forever)
# ---------------------------------------------------------------------------


def test_dspconfig_rejects_hop_greater_than_window():
    with pytest.raises(ValueError, match="hop_sec"):
        DSPConfig(window_sec=0.5, hop_sec=1.0)


def test_extractor_rejects_hop_greater_than_window():
    with pytest.raises(ValueError, match="hop_sec"):
        StreamingBandPowerExtractor(
            sample_rate=250,
            n_channels=2,
            config=DSPConfig(window_sec=0.5, hop_sec=1.0),
        )


def test_extractor_accepts_hop_equal_window():
    """hop == window (non-overlapping) is valid and must not hang."""
    ext = StreamingBandPowerExtractor(
        sample_rate=250,
        n_channels=1,
        config=DSPConfig(window_sec=0.5, hop_sec=0.5),
    )
    # exactly one full window → one emission; a 250-sample chunk would emit 2
    results = ext.feed_chunk(np.ones((1, 125)))
    assert len(results) == 1
    assert results[0][0].alpha >= 0.0


def test_advance_buffer_rejects_negative_keep():
    """Direct mutation of hop_samples past window_samples must raise, not
    silently set a negative buffer length."""
    ext = StreamingBandPowerExtractor(sample_rate=250, n_channels=1)
    ext._hop_samples = ext._window_samples + 10
    with pytest.raises(ValueError, match="hop_samples"):
        ext._advance_buffer()


# ---------------------------------------------------------------------------
# Fix 2 — odd nperseg must double the last (interior) rfft bin, like scipy
# ---------------------------------------------------------------------------


def test_manual_welch_parity_with_scipy_even_and_odd_nperseg():
    scipy_signal = pytest.importorskip("scipy.signal")
    rng = np.random.default_rng(0)
    fs = 250

    for nperseg in (256, 255, 257):
        step = nperseg - nperseg // 2
        # Signal length exactly aligned to the segment grid → scipy does not
        # zero-pad a tail segment, so both implementations see the same set
        # of windows.
        n = nperseg + 14 * step
        signal = rng.normal(size=n)

        f1, p1 = _manual_welch_psd(signal, fs, nperseg=nperseg)
        f2, p2 = scipy_signal.welch(signal, fs=fs, nperseg=nperseg)

        np.testing.assert_allclose(f1, f2, rtol=1e-12)
        np.testing.assert_allclose(p1, p2, rtol=1e-8)


def test_odd_nperseg_has_no_nyquist_bin_and_doubles_it():
    """Direct invariant check for the regression (no scipy needed):
    for odd nperseg the last rfft bin is an interior frequency < Nyquist,
    so the one-sided doubling must cover it."""
    rng = np.random.default_rng(0)
    signal = rng.normal(size=512)
    fs = 250

    for nperseg in (255, 257):
        freqs, _ = _manual_welch_psd(signal, fs, nperseg=nperseg)
        assert freqs[-1] < fs / 2.0
