"""Dual LSL stream generator for offline dual-device validation.

Publishes two synthetic EEG outlets that mimic the two production bridges:

- ``gtec_bci_core4``    — 4 channels  (BCI Core-4 Headband: F8, Fp2, Fp1, F7)
- ``gtec_hybrid_black`` — 8 channels (Unicorn Hybrid Black: Fz, C3, Cz, C4,
  Pz, PO7, Oz, PO8)

Both 250 Hz, type=EEG, float32, source_unit=uV. Every channel is a mix of
alpha/theta/beta sinusoids plus noise; ``--blink`` periodically injects a
large EOG-like transient that drives the metric blink detector.

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


def _synthetic_block(rng: np.random.Generator, n_samples: int, n_channels: int) -> np.ndarray:
    """µV-scale synthetic EEG: alpha/theta/beta tones + gaussian noise."""
    t = np.arange(n_samples) / SAMPLE_RATE
    phase = rng.uniform(0, 2 * np.pi, size=n_channels)
    base = (
        6.0 * np.sin(2 * np.pi * 10.0 * t[:, None] + phase)                  # alpha
        + 3.0 * np.sin(2 * np.pi * 6.0 * t[:, None] + 1.3 * phase)           # theta
        + 2.0 * np.sin(2 * np.pi * 20.0 * t[:, None] + 0.7 * phase)          # beta
    )
    return base + rng.normal(0.0, 2.0, size=(n_samples, n_channels))


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
        outlets.append((source_id, len(labels), StreamOutlet(info)))
        print(f"streaming {source_id}: {len(labels)} ch @ {SAMPLE_RATE:g} Hz")

    rng = np.random.default_rng(42)
    start = time.time()
    next_blink_at = start + 5.0
    try:
        while True:
            if args.duration and time.time() - start >= args.duration:
                break
            for source_id, n_ch, outlet in outlets:
                chunk = _synthetic_block(rng, CHUNK_SIZE, n_ch)
                if args.blink and time.time() >= next_blink_at:
                    # EOG-like transient on the first sample of every channel
                    chunk[0, :] += 80.0
                outlet.push_chunk(chunk.astype(np.float32).tolist())
            if args.blink and time.time() >= next_blink_at:
                print("blink injected")
                next_blink_at = time.time() + 6.0
            time.sleep(CHUNK_SIZE / SAMPLE_RATE)
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
