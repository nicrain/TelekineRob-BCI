"""AlphaPolicy — uses alpha band power for speed and steering.

Algorithm
---------
- **speed_intent**: inversely proportional to ``alpha`` power.
  Alpha suppression (lower alpha) indicates cortical activation and
  higher attention, so lower alpha → higher speed intent.
  EMA smoothing (α=0.35) applied before normalisation.
- **steer_intent**: same metric as speed (alpha), mapped to [0.5, 0.75].
  Direction controlled by blink toggle.
"""
from __future__ import annotations

from typing import Dict

from thymio_control.policies.base import Policy
from thymio_control.processors.enrich import clip01


class AlphaPolicy(Policy):
    """Use alpha power for speed and steering (blink controls direction)."""

    ema_alpha: float = 0.35

    def __init__(self, offset: float = 0.0, scale: float = 1.0) -> None:
        super().__init__()
        self.alpha_offset = offset
        self.alpha_scale = scale
        self._alpha_smooth: float = 0.0
        self._primed: bool = False

    def compute_intents(self, features: Dict[str, float]) -> Dict[str, float]:
        alpha = features.get("alpha", 0.0)

        # EMA smoothing on raw alpha (before normalisation)
        if not self._primed:
            self._alpha_smooth = alpha
            self._primed = True
        else:
            self._alpha_smooth = (
                self.ema_alpha * alpha + (1.0 - self.ema_alpha) * self._alpha_smooth
            )

        # Lower alpha = more focused = faster
        alpha_norm = clip01((self._alpha_smooth - self.alpha_offset) / self.alpha_scale)
        speed_intent = clip01(1.0 - alpha_norm)

        # Steering only in the focused half (alpha_norm 0→0.5).
        # Relaxed / high alpha (alpha_norm 0.5→1.0) → no turn.
        steer_intent = max(0.5, 0.75 - alpha_norm * 0.5)
        return {"speed_intent": speed_intent, "steer_intent": steer_intent}
