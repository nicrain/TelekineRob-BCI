"""EEG device configuration registry.

A single source of truth for per-device parameters such as channel count,
sample rate, and default LSL channel-index mappings.

Usage
-----
    from thymio_control.device_profiles import get_device_config

    cfg = get_device_config("enobio-20")
    n_ch = cfg["n_channels"]   # 20
    sr   = cfg["sample_rate"]  # 500

Adding a new device
-------------------
Append an entry to ``EEG_DEVICE_CONFIGS`` with the required keys:
    - label            : human-readable name
    - n_channels       : total EEG channels
    - sample_rate      : nominal sample rate in Hz
    - channel_labels   : ordered list of channel labels
    - default_lsl_channel_map : dict mapping label → LSL sample index
"""
from __future__ import annotations

from typing import Any, Dict


EEG_DEVICE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "enobio-20": {
        "label": "Enobio 20",
        "n_channels": 20,
        "sample_rate": 500,
        "channel_labels": [
            "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
            "O1", "O2", "F7", "F8", "T7", "T8", "P7", "P8",
            "Fz", "Cz", "Pz", "Oz",
        ],
        "default_lsl_channel_map": {
            "Fp1": 0,  "Fp2": 1,  "F3": 2,   "F4": 3,
            "C3":  4,  "C4":  5,  "P3": 6,   "P4": 7,
            "O1":  8,  "O2":  9,  "F7": 10,  "F8": 11,
            "T7":  12, "T8":  13, "P7": 14,  "P8": 15,
            "Fz":  16, "Cz":  17, "Pz": 18,  "Oz": 19,
        },
    },
    "unicorn-8": {
        "label": "Unicorn Hybrid Black",
        "n_channels": 8,
        "sample_rate": 250,
        "channel_labels": ["Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8"],
        "default_lsl_channel_map": {
            "Fz": 0, "C3": 1, "Cz": 2, "C4": 3,
            "Pz": 4, "PO7": 5, "Oz": 6, "PO8": 7,
        },
    },
    "unicorn-4": {
        "label": "Unicorn BCI Core-4 Headband",
        "n_channels": 4,
        "sample_rate": 250,
        "channel_labels": ["Fz", "Cz", "Pz", "Oz"],
        "default_lsl_channel_map": {
            "Fz": 0, "Cz": 1, "Pz": 2, "Oz": 3,
        },
    },
}


def get_device_config(device_key: str) -> Dict[str, Any]:
    """Return the configuration dict for *device_key*.

    Parameters
    ----------
    device_key : str
        Case-insensitive device identifier, e.g. ``"enobio-20"``.

    Raises
    ------
    ValueError
        If *device_key* is not registered in ``EEG_DEVICE_CONFIGS``.
    """
    key = str(device_key).strip().lower()
    if key not in EEG_DEVICE_CONFIGS:
        valid = ", ".join(sorted(EEG_DEVICE_CONFIGS))
        raise ValueError(
            f"Unknown EEG device: {device_key!r}. Valid options: {valid}"
        )
    return EEG_DEVICE_CONFIGS[key]
