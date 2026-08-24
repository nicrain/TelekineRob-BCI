"""Verify dummy_dual_streams blink bursts through the real DSP pipeline.

The metric-blink detector (eeg_control_node) confirms a blink when the
policy metric stays above ``2 × p50_ref`` (= 2 × median, since
offset=p5 and scale=p50−p5) for ``blink_confirm_frames`` (2) consecutive
Welch windows. These tests feed the tool's synthetic chunks through the
same pipeline (StreamingBandPowerExtractor → band_power_to_metrics →
enrich_features → theta_beta) and assert:

1. a sustained burst produces ≥2 consecutive windows above the threshold
   (the 2-frame confirm fires);
2. the no-blink baseline never exceeds the threshold (no false positive).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "thymio_control"))  # thymio_control → inner pkg

from lsl_test.dummy_dual_streams import (  # noqa: E402
    BLINK_BURST_CHUNKS,
    CHUNK_SIZE,
    SAMPLE_RATE,
    _inject_blink,
    _signal_generator,
)
from thymio_control.processors.band_power import (  # noqa: E402
    DSPConfig,
    StreamingBandPowerExtractor,
    band_power_to_metrics,
)
from thymio_control.processors.enrich import enrich_features  # noqa: E402


def _theta_beta_series(seed: int, seconds: float, with_blink: bool) -> list[float]:
    """Feed phase-continuous synthetic chunks through the streaming extractor;
    return per-window ``theta_beta`` (the tbr calibration metric)."""
    gen = _signal_generator(4, seed)
    ext = StreamingBandPowerExtractor(
        sample_rate=int(SAMPLE_RATE),
        n_channels=4,
        config=DSPConfig(window_sec=1.0, hop_sec=0.5),
    )
    series: list[float] = []
    total_chunks = int(seconds * SAMPLE_RATE / CHUNK_SIZE)
    next_blink_at = 5.0  # seconds
    burst_left = 0
    for ci in range(total_chunks):
        chunk = next(gen)
        t = ci * CHUNK_SIZE / SAMPLE_RATE
        if burst_left > 0:
            _inject_blink(chunk)
            burst_left -= 1
        elif with_blink and t >= next_blink_at:
            burst_left = BLINK_BURST_CHUNKS
            _inject_blink(chunk)
            burst_left -= 1
            next_blink_at += 6.0
        for result in ext.feed_chunk(chunk.T):  # (n_channels, n_samples)
            metrics = band_power_to_metrics(result[0], source_unit="uV")
            features = enrich_features(metrics)
            series.append(float(features["theta_beta"]))
    return series


def _threshold(series: list[float]) -> float:
    """Production blink threshold = 2 × p50 (offset=p5, scale=p50−p5 → p50_ref=p50)."""
    p50 = float(np.percentile(np.asarray(series), 50))
    return 2.0 * p50


def test_blink_burst_triggers_two_frame_confirm():
    baseline = _theta_beta_series(7, 30.0, with_blink=False)
    thresh = _threshold(baseline)

    sig = _theta_beta_series(7, 30.0, with_blink=True)  # same seed → same underlying signal

    above = [v > thresh for v in sig]
    max_run = cur = 0
    for a in above:
        cur = cur + 1 if a else 0
        max_run = max(max_run, cur)

    assert max_run >= 2, (
        f"no 2-frame confirm: max consecutive windows above 2×p50 = {max_run}; "
        f"threshold={thresh:.3f}; "
        f"above-threshold windows={[(round(v, 2), round(t, 2)) for v, t in zip(sig, above) if t]}"
    )


def test_no_blink_baseline_does_not_false_trigger():
    baseline = _theta_beta_series(7, 30.0, with_blink=False)
    thresh = _threshold(baseline)

    assert max(baseline) < thresh, (
        f"baseline false trigger: max theta_beta={max(baseline):.3f} ≥ threshold {thresh:.3f}"
    )
