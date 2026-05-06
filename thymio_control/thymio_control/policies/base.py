"""Base Policy interface.

All concrete policies must subclass ``Policy`` and implement
``compute_intents``.

Design constraints
------------------
- Policies are **stateless** by default (no instance state).
- ``compute_intents`` must return a dict containing at least
  ``"speed_intent"`` and ``"steer_intent"``, each in the range [0, 1].
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
            Expected keys include at minimum ``beta_alpha_theta`` and
            ``alpha_asym`` (set by ``processors.enrich``).

        Returns
        -------
        dict
            Must include ``"speed_intent"`` and ``"steer_intent"`` in [0, 1].
        """
        raise NotImplementedError
