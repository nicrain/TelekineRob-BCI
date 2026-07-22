"""StreamingBlinkDetector — real-time active/passive blink classification.

Based on the method validated in Arpaia et al. (2020):
``Wearable Brain-Computer Interface instrumentation for robot-based
rehabilitation by Augmented Reality``.

Principle
---------
Voluntary (active) eye blinks produce EOG artifacts that are
substantially larger than spontaneous (passive) blinks.  The detector
uses an adaptive amplitude threshold derived from the running signal
distribution::

    threshold = median + k_mad × MAD

where MAD = median(|x - median(x)|).  A blink whose peak exceeds this
threshold is classified as **active**.  The threshold adapts to
inter-subject variability without requiring calibration.

Implementation
--------------
- **State machine**: idle → rising (above threshold) → idle (back to baseline)
- **Confirm counter**: ``N`` consecutive above-threshold samples required to
  enter *rising* state (default 3).  Rejects single-sample spikes (EMG,
  electrode pop) while real blinks (200–400 ms → 50–100 samples) pass
  through with negligible latency (~12 ms at 250 Hz).
- **Refractory period**: 500 ms lock-out after each detection
- **Channel**: single frontopolar channel (default index 0 = Fp1)
- **Buffer**: rolling window of 5 s at 250 Hz for running statistics

Accuracy (reported in paper): 91.8 ± 3.7 % on 10 subjects.
"""

from __future__ import annotations

from collections import deque
from typing import Optional

import numpy as np


class StreamingBlinkDetector:
    """Real-time active-blink detector using adaptive amplitude threshold.

    Parameters
    ----------
    sample_rate : int
        Sampling rate in Hz (250 for g.tec devices).
    channel_idx : int
        Which EEG channel to monitor (should be Fp1 or equivalent).
    buffer_sec : float
        Seconds of history for running median / MAD computation.
    k_mad : float
        Threshold multiplier.  Higher = fewer false positives.
    refractory_ms : float
        Minimum interval between successive detections.
    min_threshold : float
        Absolute floor for the adaptive threshold (µV).  Prevents false
        triggers when the EEG is very quiet (MAD → 0 collapses the
        adaptive term).  Real blinks (50–150 µV) easily exceed this.
    confirm_samples : int
        Number of consecutive above-threshold samples before entering
        the *rising* state (default 1 = immediate).  Setting to 5+
        rejects single-sample spikes (EMG, electrode pop) while adding
        only ~20 ms latency at 250 Hz.
    min_rising_samples : int
        Minimum number of samples the signal must stay in *rising* state
        before a detection is emitted (default 1).  Active blinks last
        150-200 ms (37-50 samples at 250 Hz); passive blinks last only
        60-80 ms (15-20 samples).  Setting this to ~30 (120 ms) blocks
        passive blinks while keeping active ones.
    """

    def __init__(
        self,
        sample_rate: int = 250,
        channel_idx: int = 0,
        buffer_sec: float = 5.0,
        k_mad: float = 6.0,
        refractory_ms: float = 500.0,
        stats_interval: int = 25,
        min_threshold: float = 15.0,
        confirm_samples: int = 1,
        min_rising_samples: int = 1,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {sample_rate}")
        if buffer_sec <= 0:
            raise ValueError(f"buffer_sec must be positive, got {buffer_sec}")
        if min_threshold < 0:
            raise ValueError(f"min_threshold must be non-negative, got {min_threshold}")
        if confirm_samples < 1:
            raise ValueError(f"confirm_samples must be >= 1, got {confirm_samples}")
        if min_rising_samples < 1:
            raise ValueError(f"min_rising_samples must be >= 1, got {min_rising_samples}")

        self._channel_idx = channel_idx
        self._buffer_max = int(buffer_sec * sample_rate)
        self._k_mad = k_mad
        self._refractory_len = int(refractory_ms / 1000.0 * sample_rate)
        self._stats_interval = max(1, stats_interval)
        self._min_threshold = float(min_threshold)
        self._confirm_samples = int(confirm_samples)
        self._min_rising_samples = int(min_rising_samples)

        self._buffer: deque[float] = deque(maxlen=self._buffer_max)
        self._state: str = "idle"
        self._peak_val: float = 0.0
        self._refractory_counter: int = 0
        self._sample_count: int = 0
        self._confirm_counter: int = 0
        self._rising_samples: int = 0
        self._cached_med: float = 0.0
        self._cached_mad: float = 0.0
        self._stats_age: int = self._stats_interval  # force recompute on first sample

        # Minimum samples before emitting detections
        self._warmup = min(100, self._buffer_max)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def sample_count(self) -> int:
        """Total samples processed since creation or last reset."""
        return self._sample_count

    def feed_chunk(self, chunk: np.ndarray) -> list[dict]:
        """Process ``(n_channels, n_samples)`` chunk; return active-blink events.

        Parameters
        ----------
        chunk : np.ndarray
            Shape ``(n_channels, n_samples)``.  Only the configured
            *channel_idx* row is examined.

        Returns
        -------
        list[dict]
            Each dict has keys ``sample`` (global sample index) and
            ``peak`` (peak amplitude of the detected blink).  Empty
            if no active blink was detected in this chunk.
        """
        if chunk.shape[0] <= self._channel_idx:
            return []
        row = chunk[self._channel_idx]
        events: list[dict] = []
        for val in row:
            event = self._feed_sample(float(val))
            if event is not None:
                events.append(event)
        return events

    def reset(self) -> None:
        """Clear internal buffers and state (e.g. after device reconnect)."""
        self._buffer.clear()
        self._state = "idle"
        self._peak_val = 0.0
        self._refractory_counter = 0
        self._confirm_counter = 0
        self._rising_samples = 0
        self._sample_count = 0
        self._stats_age = self._stats_interval

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _feed_sample(self, value: float) -> Optional[dict]:
        self._sample_count += 1

        # --- refractory lock-out ---
        if self._refractory_counter > 0:
            self._refractory_counter -= 1
            return None

        # --- adaptive threshold (cached, updated every stats_interval samples) ---
        # Only feed baseline (idle) samples into the statistics buffer so
        # blink EOG artifacts cannot inflate the MAD and block future
        # detections.
        if self._state == "idle":
            self._buffer.append(value)

        if len(self._buffer) < self._warmup:
            return None

        if self._stats_age >= self._stats_interval:
            arr = np.array(self._buffer, dtype=np.float64)
            self._cached_med = float(np.median(arr))
            self._cached_mad = float(np.median(np.abs(arr - self._cached_med)))
            self._stats_age = 0
        self._stats_age += 1
        threshold = max(
            self._cached_med + self._k_mad * self._cached_mad,
            self._min_threshold,
        )

        # --- state machine ---
        if self._state == "idle":
            if value > threshold:
                self._confirm_counter += 1
                if self._confirm_counter >= self._confirm_samples:
                    self._state = "rising"
                    self._peak_val = value
                    self._rising_samples = 1
                    self._confirm_counter = 0
            else:
                self._confirm_counter = 0
            return None

        # self._state == "rising"
        self._rising_samples += 1
        if value > self._peak_val:
            self._peak_val = value

        if value < self._cached_med:   # returned to baseline
            self._state = "idle"
            if (self._peak_val > threshold
                    and self._rising_samples >= self._min_rising_samples):
                self._refractory_counter = self._refractory_len
                return {"sample": self._sample_count, "peak": float(self._peak_val)}

        return None


# ---------------------------------------------------------------------------
# Dual-channel wrapper
# ---------------------------------------------------------------------------


class DualChannelBlinkDetector:
    """Run two ``StreamingBlinkDetector`` instances on different channels
    and only emit a detection when **both** register a blink within the
    same chunk.

    Rationale
    ---------
    Vertical eye blinks produce a symmetrical EOG: both Fp1 and Fp2
    see a large positive (or negative) deflection in the same direction
    at the same time.  Horizontal eye movements and unilateral EMG
    artifacts are asymmetric — one channel may spike but the other
    won't, or they'll spike in opposite directions.

    By requiring both channels to agree, we reject:

    - Eye saccades (horizontal: Fp1/Fp2 are anti-phase)
    - Unilateral EMG / electrode pops
    - Any artifact that doesn't look like a bilateral blink

    Parameters are forwarded identically to each internal detector.
    """

    def __init__(
        self, sample_rate: int, channel_indices: list[int], **kwargs,
    ) -> None:
        if len(channel_indices) < 2:
            raise ValueError(
                f"DualChannelBlinkDetector requires ≥ 2 channel indices, "
                f"got {channel_indices}"
            )
        self._dets = [
            StreamingBlinkDetector(sample_rate=sample_rate, channel_idx=ch, **kwargs)
            for ch in channel_indices
        ]

    def feed_chunk(self, chunk: "np.ndarray") -> list[dict]:
        """Process chunk through all detectors; only emit if all agree."""
        results = [d.feed_chunk(chunk) for d in self._dets]
        if all(r for r in results):
            return results[0]  # return first detector's events
        return []

    def reset(self) -> None:
        for d in self._dets:
            d.reset()
