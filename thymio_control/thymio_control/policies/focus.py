"""FocusPolicy — maps focus level and alpha asymmetry to control intents.

Algorithm
---------
- **speed_intent**: derived from ``beta_alpha_theta`` (the "engagement" ratio).
  Higher engagement → higher speed intent.
- **steer_intent**: derived from ``alpha_asym`` (right minus left alpha power,
  normalised).  Values > 0.5 indicate rightward bias; < 0.5 leftward.

Note
----
The normalisation constants (0.15 / 0.85 for focus, 1.1 for steer) are
empirical baselines for Enobio-20 at 500 Hz.  Adjust via config if needed.
"""
from __future__ import annotations

from typing import Dict

from thymio_control.policies.base import Policy
from thymio_control.processors.enrich import clip01


class FocusPolicy(Policy):
    """Map focus level and alpha lateralisation to speed / steer intents.

    Attributes are intentionally exposed as class-level defaults so they can
    be overridden in subclasses or via config injection without subclassing.
    """

    focus_offset: float = 0.15
    focus_scale:  float = 0.85
    steer_gain:   float = 1.1

    def compute_intents(self, features: Dict[str, float]) -> Dict[str, float]:
        focus = features.get("beta_alpha_theta", 0.0)
        focus_norm = clip01((focus - self.focus_offset) / self.focus_scale)

        asym = features.get("alpha_asym", 0.0)
        steer_intent = clip01(0.5 + self.steer_gain * asym)
        speed_intent = clip01(focus_norm)

        return {"speed_intent": speed_intent, "steer_intent": steer_intent}
