"""P44③: TRANSIENT metric-blink detection.

The old detector used ABSOLUTE thresholds (metric > p50×2 / metric < p5/2),
so rest-state drift (persistently high alpha/tbr, low ei) made the threshold
pass every frame → a false-blink LOOP that toggled the steer direction and
froze ``last_intents`` at a stale turn value (the car turned in rest and the
direction flipped repeatedly).

The new criterion is TRANSIENT — a spike/drop vs a SHORT-WINDOW recent
baseline (a rolling MEDIAN, robust to the 2-frame blink spike). A real blink
does not move the median; a SUSTAINED drift fills the window so the check
``val > baseline×K`` / ``val < baseline×K`` stops passing. ``confirm_frames``
consecutive outside-range frames confirm a blink (a single artifact frame is
rejected); ``holdoff_frames`` of silence follow. ``in_progress`` lets the
caller avoid freezing a stale steer value during the blink (③b).
"""
from __future__ import annotations

from collections import deque
from statistics import median


class MetricBlinkDetector:
    """Transient blink confirmation on one policy metric.

    mode 'up'  → blink is an up-spike  (alpha / tbr: EOG inflates the band).
    mode 'down'→ blink is an instant drop (ei: EOG inflates the denominator).
    """

    def __init__(
        self,
        mode: str = "up",
        window: int = 30,
        k_up: float = 2.0,
        k_down: float = 0.5,
        confirm_frames: int = 2,
        holdoff_frames: int = 4,
        min_samples: int = 15,
    ) -> None:
        self._mode = mode
        self._window = max(1, window)
        self._k_up = k_up
        self._k_down = k_down
        self._confirm_frames = max(1, confirm_frames)
        self._holdoff_frames = max(0, holdoff_frames)
        self._min_samples = max(1, min_samples)
        self._hist: deque[float] = deque(maxlen=self._window)
        self._confirm = 0
        self._holdoff = 0

    @property
    def in_progress(self) -> bool:
        """True while a blink is being confirmed or held off — the caller must
        NOT freeze a stale steer value during this window (clamp to neutral)."""
        return self._confirm > 0 or self._holdoff > 0

    def reset(self) -> None:
        self._hist.clear()
        self._confirm = 0
        self._holdoff = 0

    def update(self, value: float) -> bool:
        """Feed one metric sample; returns True when a blink is CONFIRMED
        (the caller toggles the direction exactly once)."""
        if self._holdoff > 0:
            self._holdoff -= 1
            return False
        self._hist.append(value)
        if len(self._hist) < self._min_samples:
            return False                       # baseline not primed yet
        baseline = median(self._hist)
        if baseline <= 1e-9:
            baseline = 1e-9
        if self._mode == "down":
            triggered = value < baseline * self._k_down
        else:
            triggered = value > baseline * self._k_up
        if triggered:
            self._confirm += 1
        else:
            self._confirm = 0                   # must FALL BACK before re-trigger
            return False
        if self._confirm >= self._confirm_frames:
            self._confirm = 0
            self._holdoff = self._holdoff_frames
            return True
        return False
