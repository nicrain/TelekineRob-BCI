"""TbrPolicy — uses theta/beta ratio for speed and steering.

Algorithm
---------
- **speed_intent**: inversely proportional to ``theta_beta`` (theta/beta ratio, TBR).
  A higher TBR typically indicates lower attentional engagement,
  so higher ratio → lower speed intent.  EMA smoothing (α=0.35) applied.
- **steer_intent**: same metric as speed (theta_beta), mapped to [0.5, 0.75].
  Direction controlled by blink toggle.
"""
from __future__ import annotations

from typing import Dict

from thymio_control.policies.base import Policy
from thymio_control.processors.enrich import clip01


class TbrPolicy(Policy):
    """Use theta/beta ratio for speed and steering (blink controls direction)."""

    ema_alpha: float = 0.35

    def __init__(self, offset: float = 0.0, scale: float = 1.0) -> None:
        super().__init__()
        self.tbr_offset = offset
        self.tbr_scale = scale
        self._tbr_smooth: float = 0.0
        self._primed: bool = False

    def set_calibration(self, offset: float, scale: float) -> None:
        self.tbr_offset = offset
        self.tbr_scale = scale

    def compute_intents(self, features: Dict[str, float]) -> Dict[str, float]:
        ratio = features.get("theta_beta", 1.0)

        # EMA smoothing on raw theta_beta (before normalisation)
        if not self._primed:
            self._tbr_smooth = ratio
            self._primed = True
        else:
            self._tbr_smooth = (
                self.ema_alpha * ratio + (1.0 - self.ema_alpha) * self._tbr_smooth
            )

        # Higher TBR = less focused = slower
        tbr_norm = clip01((self._tbr_smooth - self.tbr_offset) / self.tbr_scale)
        speed_intent = clip01(1.0 - tbr_norm)

        # Steering only in the focused half (tbr_norm 0→0.5).
        # Relaxed / distracted (tbr_norm 0.5→1.0) → no turn.
        steer_intent = max(0.5, 0.75 - tbr_norm * 0.5)

        return {"speed_intent": speed_intent, "steer_intent": steer_intent}
