"""Feature enrichment — derive composite EEG metrics from raw band powers.

All public functions are **pure** (no side effects, no global state) and
accept / return plain ``dict[str, float]``.
"""
from __future__ import annotations

from typing import Dict


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def clip01(v: float) -> float:
    """Clip *v* to the closed interval [0, 1]."""
    return max(0.0, min(1.0, float(v)))


def safe_div(a: float, b: float, eps: float = 1e-9) -> float:
    """Divide *a* by *b* safely, adding *eps* to the denominator."""
    return float(a) / float(b + eps)


# ---------------------------------------------------------------------------
# Feature enrichment
# ---------------------------------------------------------------------------

def enrich_features(metrics: Dict[str, float]) -> Dict[str, float]:
    """Derive composite features from a raw metrics dict.

    Adds ``theta_beta``, ``beta_alpha``, ``beta_alpha_theta``, and
    ``alpha_asym`` so policy classes can remain simple look-ups.
    """
    f = dict(metrics)
    alpha       = f.get("alpha", 0.0)
    theta       = f.get("theta", 0.0)
    beta        = f.get("beta",  0.0)
    left_alpha  = f.get("left_alpha",  alpha * 0.5)
    right_alpha = f.get("right_alpha", alpha * 0.5)

    f["theta_beta"]      = safe_div(theta, beta)
    f["beta_alpha"]      = safe_div(beta, alpha)
    f["beta_alpha_theta"] = safe_div(beta, alpha + theta)
    f["alpha_asym"]      = safe_div(
        right_alpha - left_alpha,
        right_alpha + left_alpha,
    )
    return f
