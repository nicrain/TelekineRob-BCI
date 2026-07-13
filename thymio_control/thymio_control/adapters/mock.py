"""KeyboardAdapter — for interactive testing."""
from __future__ import annotations

import logging
import time
from typing import Optional

from thymio_control.adapters.base import BaseAdapter
from thymio_control.contracts import EegFrame

_log = logging.getLogger(__name__)


class KeyboardAdapter(BaseAdapter):
    """Return fixed EEG metrics (can be mutated externally for testing).

    Intended for interactive debugging: the caller can modify
    ``adapter.metrics`` directly to simulate different brain states.
    """

    def __init__(self) -> None:
        self.metrics = {
            "alpha":       0.5,
            "theta":       0.5,
            "beta":        0.5,
            "left_alpha":  0.5,
            "right_alpha": 0.5,
        }
        _log.info("KeyboardAdapter initialised. Modify .metrics to simulate EEG.")

    def read_frame(self) -> Optional[EegFrame]:
        return EegFrame(ts=time.time(), source="keyboard", metrics=self.metrics)
