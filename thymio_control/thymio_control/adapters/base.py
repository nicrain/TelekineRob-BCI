"""BaseAdapter interface — all input adapters must implement this contract."""
from __future__ import annotations

from typing import Optional

from thymio_control.contracts import EegFrame


class BaseAdapter:
    """Abstract base class for all EEG input adapters.

    An adapter is responsible for reading one frame of data from an input
    source and returning it as a standardised ``EegFrame``.  Returning
    ``None`` signals that no data is available in this polling cycle.
    """

    def read_frame(self) -> Optional[EegFrame]:
        """Read and return the next available frame.

        Returns
        -------
        EegFrame or None
            ``None`` if no complete frame is available yet.
        """
        raise NotImplementedError
