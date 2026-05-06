"""Compatibility shim — re-exports from thymio_control.adapters.lsl_raw.

This module was the Phase 1 experimental implementation of RawLslAdapter.
Phase 3 consolidation: all logic now lives in the production package at
``thymio_control/thymio_control/adapters/lsl_raw.py``.

This file is kept as a **thin re-export layer** so that:
- All ``lsl_test/test_*.py`` imports continue to work unchanged.
- Demo notebooks and E2E scripts stay runnable.
- A single source of truth exists in the production package.

DO NOT add new logic here — add it to
``thymio_control/thymio_control/adapters/lsl_raw.py`` instead.
"""
# Re-export the production class unchanged.
from thymio_control.adapters.lsl_raw import RawLslAdapter  # noqa: F401

__all__ = ["RawLslAdapter"]
