"""Calibration write-back logic for the EEG control node.

Pure (no ROS imports) so the sample threshold decision and the params-file
write are unit-testable on a machine without rclpy.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# Minimum samples to accept a calibration. The node collects windows at the
# hop cadence (~1.9 Hz), so 30 s yields ~57-60 samples; 50 leaves margin
# against a cold-start dip (59 was occasionally rejected at 60).
MIN_CALIB_SAMPLES = 50


def enough_samples(n: int) -> bool:
    """Whether *n* collected samples pass the calibration threshold."""
    return n >= MIN_CALIB_SAMPLES


def write_calib_result(
    cfg_roots: list[Path],
    calib_config_file: str,
    *,
    offset: float | None = None,
    scale: float | None = None,
) -> bool:
    """Write the calibration result to every config root.

    On success *offset* / *scale* are written and ``calibrate`` cleared. On
    abort (offset/scale omitted) only ``calibrate=false`` is written — so
    the frontend's poll sees calibrate==false and un-hangs instead of being
    stuck at "Calibrating… 0s".

    Returns True when every write succeeded; never raises (each root is
    guarded so any failure degrades to a log, not a hung UI).
    """
    ok = True
    for cfg_root in cfg_roots:
        try:
            cfg_file = cfg_root / calib_config_file
            with cfg_file.open("r", encoding="utf-8") as fhand:
                doc = yaml.safe_load(fhand) or {}
            params = doc.setdefault("/**", {}).setdefault("ros__parameters", {})
            if offset is not None:
                params["calib_offset"] = float(offset)
            if scale is not None:
                params["calib_scale"] = float(scale)
            params["calibrate"] = False
            with cfg_file.open("w", encoding="utf-8") as fhand:
                yaml.safe_dump(doc, fhand, sort_keys=False, allow_unicode=False)
        except Exception:
            ok = False
    return ok
