"""ThetaBetaPolicy — uses theta/beta ratio for speed and alpha asymmetry for steering.

Algorithm
---------
- **speed_intent**: inversely proportional to ``theta_beta`` (theta/beta ratio, TBR).
  A higher TBR typically indicates lower attentional engagement,
  so higher ratio → lower speed intent.  EMA smoothing (α=0.35) applied.
- **steer_intent**: same alpha asymmetry mapping as FocusPolicy.

Calibration
-----------
Parameters calibrated against ``20260408111446_Patient01.edf`` (3-min window).
Re-calibrate for different recordings.
"""
from __future__ import annotations

from typing import Dict

from thymio_control.policies.base import Policy
from thymio_control.processors.enrich import clip01


class ThetaBetaPolicy(Policy):
    """Use theta/beta ratio for speed intent and alpha asymmetry for steering."""

    # Normalisation: clip01(1.0 - (ratio_smooth - offset) / scale)
    # Calibrated to map p5~p95 of theta_beta to [0, 1]
    tbr_offset: float = 0.207    # p5 of theta_beta
    tbr_scale:  float = 2.215    # p95 - p5
    steer_gain: float = 1.1
    ema_alpha:  float = 0.35

    def __init__(self) -> None:
        super().__init__()
        self._tbr_smooth: float = 0.0
        self._primed: bool = False

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

        asym = features.get("alpha_asym", 0.0)
        steer_intent = 0.5  # steering disabled — forward/backward only
        # steer_intent = clip01(0.5 + self.steer_gain * asym)

        return {"speed_intent": speed_intent, "steer_intent": steer_intent}
