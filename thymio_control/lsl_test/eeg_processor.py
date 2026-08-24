"""Compatibility shim — re-exports from thymio_control.processors.band_power.

This module was the Phase 1 experimental implementation.
Phase 3 consolidation: all logic now lives in the production package at
``thymio_control/thymio_control/processors/band_power.py``.

This file is kept as a **thin re-export layer** so that:
- All ``lsl_test/test_*.py`` imports continue to work unchanged.
- Demo notebooks stay runnable without code modification.
- A single source of truth exists in the production package.

DO NOT add new logic here — add it to
``thymio_control/thymio_control/processors/band_power.py`` instead.
"""
# Re-export everything from the production module.
from thymio_control.processors.band_power import (  # noqa: F401
    BANDS,
    BandPowers,
    DSPConfig,
    StreamingBandPowerExtractor,
    _UNIT_TO_UV,
    _band_power_from_psd,
    _hanning_window,
    _manual_welch_psd,
    band_power_to_metrics,
    compute_band_powers,
    compute_channel_band_powers,
    convert_power_to_uv2,
)

__all__ = [
    "BANDS",
    "BandPowers",
    "DSPConfig",
    "StreamingBandPowerExtractor",
    "band_power_to_metrics",
    "compute_band_powers",
    "compute_channel_band_powers",
    "convert_power_to_uv2",
]