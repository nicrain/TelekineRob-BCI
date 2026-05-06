"""Feature enrichment — derive composite EEG metrics from raw band powers.

This module migrates ``enrich_features`` and related helpers from the
monolithic ``eeg_control_pipeline.py`` so that the policy layer can stay
thin and purely rule-based.

All public functions are **pure** (no side effects, no global state) and
accept / return plain ``dict[str, float]`` so they can be used both in the
streaming real-time path and in offline Jupyter notebooks.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Sequence


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def clip01(v: float) -> float:
    """Clip *v* to the closed interval [0, 1]."""
    return max(0.0, min(1.0, float(v)))


def safe_div(a: float, b: float, eps: float = 1e-9) -> float:
    """Divide *a* by *b* safely, adding *eps* to the denominator."""
    return float(a) / float(b + eps)


def _sequence_mean(values: Any) -> float:
    """Return the arithmetic mean of *values* (iterable or scalar)."""
    try:
        iterator = iter(values)
    except TypeError:
        return float(values)

    total = 0.0
    count = 0
    for value in iterator:
        total += float(value)
        count += 1

    if count == 0:
        raise ValueError("cannot compute mean of an empty sequence")
    return total / count


def _select_channels(raw_data: Any, selected_channels: Sequence[int]) -> Any:
    """Slice *raw_data* by channel indices.

    Raises
    ------
    ValueError
        If *selected_channels* is empty.
    IndexError
        If any index is out of bounds.
    """
    if not selected_channels:
        raise ValueError("selected_channels must not be empty")

    total_channels = len(raw_data)
    for index in selected_channels:
        if index < 0 or index >= total_channels:
            raise IndexError(f"selected channel index out of bounds: {index}")

    try:
        return raw_data[list(selected_channels)]
    except Exception:
        return [raw_data[index] for index in selected_channels]


# ---------------------------------------------------------------------------
# Feature enrichment
# ---------------------------------------------------------------------------

def enrich_features(metrics: Dict[str, float]) -> Dict[str, float]:
    """Derive composite features from a raw metrics dict.

    Adds ``theta_beta``, ``beta_alpha``, ``beta_alpha_theta``, and
    ``alpha_asym`` so policy classes can remain simple look-ups.

    Parameters
    ----------
    metrics : dict
        Should contain at minimum ``"alpha"``, ``"beta"``, ``"theta"``.
        Optional keys: ``"left_alpha"``, ``"right_alpha"`` (if absent,
        each defaults to half of ``"alpha"``).

    Returns
    -------
    dict
        A **new** dict with the original keys plus the derived features.
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


# ---------------------------------------------------------------------------
# Pipeline algorithms (channel-level feature computation)
# ---------------------------------------------------------------------------

def _theta_beta_ratio_algorithm(filtered_data: Any) -> float:
    if len(filtered_data) < 2:
        raise ValueError("theta_beta_ratio requires at least two selected channels")
    theta_channel = filtered_data[0]
    beta_channel  = filtered_data[1]
    return safe_div(_sequence_mean(theta_channel), _sequence_mean(beta_channel))


PIPELINE_ALGORITHMS: Dict[str, Callable[[Any], float]] = {
    "theta_beta_ratio": _theta_beta_ratio_algorithm,
}


def compute_pipeline_feature(
    raw_data: Any,
    selected_channels: Sequence[int],
    algorithm_name: str,
) -> float:
    """Slice channels then apply a named feature algorithm.

    Parameters
    ----------
    raw_data : array-like
        Multi-channel data indexed by channel first.
    selected_channels : sequence of int
        Channel indices to feed into the algorithm.
    algorithm_name : str
        Key in ``PIPELINE_ALGORITHMS`` (e.g. ``"theta_beta_ratio"``).

    Raises
    ------
    ValueError
        If *algorithm_name* is not registered.
    """
    filtered_data = _select_channels(raw_data, selected_channels)
    algorithm = PIPELINE_ALGORITHMS.get(str(algorithm_name))
    if algorithm is None:
        raise ValueError(f"Unsupported pipeline algorithm: {algorithm_name!r}")
    return float(algorithm(filtered_data))
