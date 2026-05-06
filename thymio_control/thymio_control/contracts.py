"""Data contracts for the Thymio EEG control pipeline.

This module defines the standard data structures that flow between layers:

    Input source → Adapter → Processor → Policy → Controller

Design notes
------------
- ``EegFrame`` is kept as the primary inter-layer contract for backward
  compatibility with existing code.  The ``metrics`` dict is intentionally
  flexible so each adapter / processor can enrich it without schema changes.
- Future structured types (``RawSampleFrame``, ``FeatureFrame``,
  ``ControlFrame``) are planned for Phase 3 once the real-time path is stable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


# ---------------------------------------------------------------------------
# Primary inter-layer contract
# ---------------------------------------------------------------------------

@dataclass
class EegFrame:
    """Unified EEG data frame passed between pipeline layers.

    Attributes
    ----------
    ts : float
        Unix timestamp (seconds) when the frame was produced.
    source : str
        Identifier of the adapter that produced this frame
        (e.g. ``"lsl_raw"``, ``"tcp_client"``, ``"mock"``).
    metrics : Dict[str, float]
        Named numeric metrics.  Required keys depend on the active policy;
        adapters should populate at minimum ``alpha``, ``beta``, ``theta``.
    """

    ts: float
    source: str
    metrics: Dict[str, float]


# ---------------------------------------------------------------------------
# Placeholders for Phase 3 (kept here so imports are stable early)
# ---------------------------------------------------------------------------

# RawSampleFrame  – raw ADC samples from a single chunk
# FeatureFrame    – band-power features after DSP
# ControlFrame    – speed_intent / steer_intent after policy
#
# These will be added when the real-time path is validated in Phase 3.
