"""Dual LSL stream generator for offline dual-device validation.

Publishes two synthetic EEG outlets that mimic the two production bridges:

- ``gtec_bci_core4``    — 4 channels  (BCI Core-4 Headband: F8, Fp2, Fp1, F7)
- ``gtec_hybrid_black`` — 8 channels (Unicorn Hybrid Black: Fz, C3, Cz, C4,
  Pz, PO7, Oz, PO8)

Both 250 Hz, type=EEG, float32, source_unit=uV. Every channel is a mix of
alpha/theta/beta sinusoids plus noise; ``--blink`` injects a **sustained
EOG-like burst** (~450 ms) that raises the theta/beta metric above the
calibrated median reference for two consecutive Welch windows — the
condition the production metric-blink detector confirms on.

Note: a single-sample spike does NOT trigger the metric blink — its energy
is spread across all bands by Welch and the beta-band inflation lowers
theta_beta. Hence the burst, not a sample.

Offline validation tool only (lsl_test/), not part of the production path.
Usage::

    python lsl_test/dummy_dual_streams.py --blink
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

import numpy as np


SAMPLE_RATE = 250.0
CHUNK_SIZE = 16  # matches the production bridges' push granularity

# source_id → channel labels (mirrors gtec_bridge + AGENTS.md device tables)
STREAMS = [
    ("gtec_bci_core4", ["F8", "Fp2", "Fp1", "F7"]),
    ("gtec_hybrid_black", ["Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8"]),
]

# Blink burst: a **contiguous** ~450 ms sustained EOG-like step (~112 samples
# at CHUNK_SIZE=16 / 250 Hz ≈ 7 fully-boosted chunks). A contiguous step has
# low-frequency (1/f) content that inflates the theta band and raises
# theta_beta. Boosting only part of each chunk would instead create a ~16 Hz
# square wave in the beta band, LOWERING theta_beta (the reviewer's note).
BLINK_BURST_CHUNKS = 7
BLINK_BOOST_SAMPLES = CHUNK_SIZE  # whole chunk → contiguous burst
BLINK_AMPLITUDE = 80.0  # µV

# Noise amplitude kept low and beta made tone-dominated (M5-1b) so the
# no-blink theta_beta baseline stays well below the 2× median blink
# threshold — otherwise the wide beta band's noise floor makes the ratio
# (theta/beta) unstable and occasionally false-triggers.
NOISE_STD = 0.4  # µV


def _signal_generator(n_channels: int, seed: int):
    """Yield phase-continuous ``CHUNK_SIZE``-sample synthetic EEG chunks.

    The tones share a single global time base (no per-chunk phase restart),
    so the Welch band powers are stable window-to-window — the beta
    denominator stays put and the no-blink theta_beta baseline does not
    wander. A blink burst on top of this is a clean, detectable transient.
    """
    rng = np.random.default_rng(seed)
    phase = rng.uniform(0, 2 * np.pi, size=n_channels)
    t = 0.0
    while True:
        tt = t + np.arange(CHUNK_SIZE) / SAMPLE_RATE
        base = (
            6.0 * np.sin(2 * np.pi * 10.0 * tt[:, None] + phase)            # alpha
            + 4.0 * np.sin(2 * np.pi * 6.0 * tt[:, None] + 1.3 * phase)     # theta
            + 6.0 * np.sin(2 * np.pi * 20.0 * tt[:, None] + 0.7 * phase)    # beta (strong, stable denominator)
        )
        yield base + rng.normal(0.0, NOISE_STD, size=(CHUNK_SIZE, n_channels))
        t += CHUNK_SIZE / SAMPLE_RATE


def _inject_blink(chunk: np.ndarray) -> np.ndarray:
    """Add the EOG-like burst step to the first samples of *chunk* (in place)."""
    chunk[:BLINK_BOOST_SAMPLES, :] += BLINK_AMPLITUDE
    return chunk


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--blink", action="store_true",
        help="periodically inject EOG-like spikes (triggers metric blink)",
    )
    parser.add_argument(
        "--duration", type=float, default=0.0,
        help="stop after this many seconds (0 = run until Ctrl+C)",
    )
    args = parser.parse_args(argv)

    from pylsl import StreamInfo, StreamOutlet  # lazy: module importable without pylsl

    outlets = []
    for source_id, labels in STREAMS:
        info = StreamInfo(
            name=f"{source_id.removeprefix('gtec_')}_EEG",
            type="EEG",
            channel_count=len(labels),
            nominal_srate=SAMPLE_RATE,
            channel_format="float32",
            source_id=source_id,
        )
        desc = info.desc()
        desc.append_child_value("channel_labels", ",".join(labels))
        desc.append_child_value("source_unit", "uV")
        outlets.append((source_id, StreamOutlet(info)))
        print(f"streaming {source_id}: {len(labels)} ch @ {SAMPLE_RATE:g} Hz")

    # One phase-continuous signal generator per outlet (same seed → identical
    # waveform on the first channels; blink is injected into both).
    gens = {source_id: _signal_generator(len(labels), seed=42) for source_id, labels in STREAMS}

    start = time.time()
    next_blink_at = start + 5.0
    burst_remaining = 0
    try:
        while True:
            if args.duration and time.time() - start >= args.duration:
                break
            for source_id, outlet in outlets:
                chunk = next(gens[source_id]).copy()
                if burst_remaining > 0:
                    _inject_blink(chunk)
                outlet.push_chunk(chunk.astype(np.float32).tolist())
            if burst_remaining > 0:
                burst_remaining -= 1
            elif args.blink and time.time() >= next_blink_at:
                burst_remaining = BLINK_BURST_CHUNKS  # ~450 ms sustained burst
                print("blink burst started")
                next_blink_at = time.time() + 6.0
            time.sleep(CHUNK_SIZE / SAMPLE_RATE)
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
