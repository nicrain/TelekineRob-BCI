"""Base Policy interface.

All concrete policies must subclass ``Policy`` and implement
``compute_intents``.

Design constraints
------------------
- Policies hold per-instance **EMA smoothing state** (``_<metric>_smooth``)
  plus calibration ``offset``/``scale``; they are not stateless.
- ``compute_intents`` must return a dict containing at least
  ``"speed_intent"`` and ``"steer_intent"``, each in the range [0, 1].
- Calibration must call :meth:`set_calibration` to update offset/scale
  **in place** — rebuilding the instance would reset the EMA state and
  cause an intent jump right after calibration.
"""
from __future__ import annotations

from typing import Dict


class Policy:
    """Abstract base class for EEG control policies.

    Subclasses translate enriched EEG feature dicts into robot control
    intents that are then serialized and sent over UDP to the gaze-control
    node.
    """

    def compute_intents(self, features: Dict[str, float]) -> Dict[str, float]:
        """Compute control intents from enriched EEG features.

        Parameters
        ----------
        features : dict
            Enriched EEG metrics (output of ``enrich_features``).
            Expected keys include ``theta_beta`` and ``beta_alpha_theta``.

        Returns
        -------
        dict
            Must include ``"speed_intent"`` and ``"steer_intent"`` in [0, 1].
        """
        raise NotImplementedError

    def set_calibration(self, offset: float, scale: float) -> None:
        """Update the calibration offset/scale without resetting EMA state."""
        raise NotImplementedError
