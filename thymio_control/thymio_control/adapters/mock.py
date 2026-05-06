"""MockAdapter and KeyboardAdapter — for development and offline testing."""
from __future__ import annotations

import logging
import math
import time
from typing import Optional

from thymio_control.adapters.base import BaseAdapter
from thymio_control.contracts import EegFrame

_log = logging.getLogger(__name__)


class MockAdapter(BaseAdapter):
    """Generate synthetic EEG frames using smooth sinusoidal signals.

    Useful for rapid integration testing without physical hardware.
    The signals are designed to exercise both the speed and steer channels
    of the policy layer.
    """

    def __init__(self) -> None:
        self._t0 = time.time()

    def read_frame(self) -> Optional[EegFrame]:
        t = time.time() - self._t0
        alpha      = 12.0 + 3.0 * math.sin(0.8 * t)
        theta      =  7.0 + 2.0 * math.sin(0.5 * t + 1.2)
        beta       =  9.0 + 2.5 * math.sin(1.1 * t + 0.5)
        left_alpha = alpha * (0.95 + 0.08 * math.sin(0.4 * t))
        right_alpha = alpha * (1.05 + 0.08 * math.sin(0.4 * t + 2.2))
        return EegFrame(
            ts=time.time(),
            source="mock",
            metrics={
                "alpha":       alpha,
                "theta":       theta,
                "beta":        beta,
                "left_alpha":  left_alpha,
                "right_alpha": right_alpha,
            },
        )


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
