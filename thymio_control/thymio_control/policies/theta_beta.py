"""ThetaBetaPolicy — uses theta/beta ratio for speed and alpha asymmetry for steering.

Algorithm
---------
- **speed_intent**: inversely proportional to ``theta_beta``.
  A higher theta/beta ratio typically indicates lower attentional engagement,
  so higher ratio → lower speed intent.
- **steer_intent**: same alpha asymmetry mapping as FocusPolicy.
"""
from __future__ import annotations

from typing import Dict

from thymio_control.policies.base import Policy
from thymio_control.processors.enrich import clip01


class ThetaBetaPolicy(Policy):
    """Use theta/beta ratio for speed intent and alpha asymmetry for steering."""

    def compute_intents(self, features: Dict[str, float]) -> Dict[str, float]:
        ratio = features.get("theta_beta", 1.0)
        # Higher ratio → lower attention → lower speed
        speed_intent = clip01(1.0 - (ratio - 0.5) / 2.0)
        steer_intent = clip01(0.5 + 1.1 * features.get("alpha_asym", 0.0))
        return {"speed_intent": speed_intent, "steer_intent": steer_intent}
