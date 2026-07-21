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
        Which EEG channel to monitor (default 0 = Fp1).
    buffer_sec : float
        Seconds of history for running median / MAD computation.
    k_mad : float
        Threshold multiplier.  Higher = fewer false positives.
    refractory_ms : float
        Minimum interval between successive detections.
    """

    def __init__(
        self,
        sample_rate: int = 250,
        channel_idx: int = 0,
        buffer_sec: float = 5.0,
        k_mad: float = 6.0,
        refractory_ms: float = 500.0,
        stats_interval: int = 25,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {sample_rate}")
        if buffer_sec <= 0:
            raise ValueError(f"buffer_sec must be positive, got {buffer_sec}")

        self._channel_idx = channel_idx
        self._buffer_max = int(buffer_sec * sample_rate)
        self._k_mad = k_mad
        self._refractory_len = int(refractory_ms / 1000.0 * sample_rate)
        self._stats_interval = max(1, stats_interval)

        self._buffer: deque[float] = deque(maxlen=self._buffer_max)
        self._state: str = "idle"
        self._peak_val: float = 0.0
        self._refractory_counter: int = 0
        self._sample_count: int = 0
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
        self._sample_count = 0
        self._stats_age = self._stats_interval

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _feed_sample(self, value: float) -> Optional[dict]:
        self._sample_count += 1

        # --- maintain rolling buffer (deque with maxlen auto-evicts oldest) ---
        self._buffer.append(value)

        # --- refractory lock-out ---
        if self._refractory_counter > 0:
            self._refractory_counter -= 1
            return None

        # --- warm-up ---
        if len(self._buffer) < self._warmup:
            return None

        # --- adaptive threshold (cached, updated every stats_interval samples) ---
        if self._stats_age >= self._stats_interval:
            arr = np.array(self._buffer, dtype=np.float64)
            self._cached_med = float(np.median(arr))
            self._cached_mad = float(np.median(np.abs(arr - self._cached_med)))
            self._stats_age = 0
        self._stats_age += 1
        threshold = self._cached_med + self._k_mad * self._cached_mad

        # --- state machine ---
        if self._state == "idle":
            if value > threshold:
                self._state = "rising"
                self._peak_val = value
            return None

        # self._state == "rising"
        if value > self._peak_val:
            self._peak_val = value

        if value < self._cached_med:   # returned to baseline
            self._state = "idle"
            if self._peak_val > threshold:
                self._refractory_counter = self._refractory_len
                return {"sample": self._sample_count, "peak": float(self._peak_val)}

        return None
