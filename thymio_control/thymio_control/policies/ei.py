"""EiPolicy — maps focus level to speed and steering.

Algorithm
---------
- **speed_intent**: derived from ``beta_alpha_theta`` (the "engagement" ratio).
  Higher engagement → higher speed intent.  EMA smoothing (α=0.35) applied
  to the raw ratio before normalisation to reduce frame-to-frame jitter.
- **steer_intent**: same metric as speed (beta_alpha_theta), mapped to [0.5, 0.75].
  Direction controlled by blink toggle.

Note
----
The normalisation constants are calibrated against
``20260408111446_Patient01.edf`` (3-min stats: p5=0.323, p95=2.359).
Re-calibrate for different recordings.
"""
from __future__ import annotations

from typing import Dict

from thymio_control.policies.base import Policy
from thymio_control.processors.enrich import clip01


class EiPolicy(Policy):
    """Map focus level to speed / steer intents (blink controls direction)."""

    focus_offset: float = 0.3230
    focus_scale:  float = 2.0355
    ema_alpha:    float = 0.35

    def __init__(self, offset: float = 0.323, scale: float = 2.036) -> None:
        super().__init__()
        self.focus_offset = offset
        self.focus_scale = scale
        self._bat_smooth: float = 0.0
        self._primed: bool = False

    def compute_intents(self, features: Dict[str, float]) -> Dict[str, float]:
        focus = features.get("beta_alpha_theta", 0.0)

        # EMA smoothing on raw beta_alpha_theta (before normalisation)
        if not self._primed:
            self._bat_smooth = focus
            self._primed = True
        else:
            self._bat_smooth = (
                self.ema_alpha * focus + (1.0 - self.ema_alpha) * self._bat_smooth
            )

        focus_norm = clip01((self._bat_smooth - self.focus_offset) / self.focus_scale)

        speed_intent = clip01(focus_norm)
        # Steering only in the focused half (focus_norm 0.5→1.0).
        # Unfocused (focus_norm 0→0.5) → no turn.
        steer_intent = max(0.5, 0.25 + focus_norm * 0.5)

        return {"speed_intent": speed_intent, "steer_intent": steer_intent}
