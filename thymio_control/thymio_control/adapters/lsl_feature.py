"""LslFeatureAdapter — reads pre-computed band features from an LSL stream.

This is the "thin shell" adapter that expects upstream software (e.g. NIC2)
to have already computed band powers and pushed them as a feature vector.
It is distinct from ``RawLslAdapter``, which performs DSP internally.

Channel map example::

    channel_map = {"alpha": 0, "theta": 1, "beta": 2,
                   "left_alpha": 3, "right_alpha": 4}
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from thymio_control.adapters.base import BaseAdapter
from thymio_control.contracts import EegFrame

_log = logging.getLogger(__name__)


class LslFeatureAdapter(BaseAdapter):
    """Pull a pre-computed EEG feature vector from an LSL stream.

    Parameters
    ----------
    stream_type : str
        LSL stream type to resolve (e.g. ``"EEG"``).
    timeout : float
        Seconds to wait when discovering the stream.
    channel_map : dict
        Mapping of feature name → sample index within each LSL sample.
    """

    def __init__(
        self,
        stream_type: str,
        timeout: float,
        channel_map: Dict[str, int],
    ) -> None:
        try:
            from pylsl import StreamInlet, resolve_byprop  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "pylsl is required for LslFeatureAdapter. "
                "Install with: pip install pylsl"
            ) from exc

        streams = resolve_byprop("type", stream_type, timeout=timeout)
        if not streams:
            raise RuntimeError(f"No LSL stream found for type={stream_type}")

        self._inlet       = StreamInlet(streams[0], max_chunklen=32)
        self._channel_map = channel_map
        info = self._inlet.info()
        _log.info(
            "LslFeatureAdapter connected: name=%s type=%s channels=%d",
            info.name(), info.type(), info.channel_count(),
        )

    def read_frame(self) -> Optional[EegFrame]:
        sample, _ = self._inlet.pull_sample(timeout=0.05)
        if sample is None:
            return None

        arr = [float(v) for v in sample]
        metrics: Dict[str, float] = {}
        for name, idx in self._channel_map.items():
            if idx < 0 or idx >= len(arr):
                raise ValueError(
                    f"LSL channel '{name}' index {idx} out of bounds "
                    f"(sample length {len(arr)})"
                )
            metrics[name] = arr[idx]

        if not metrics:
            return None

        return EegFrame(ts=time.time(), source="lsl_feature", metrics=metrics)
