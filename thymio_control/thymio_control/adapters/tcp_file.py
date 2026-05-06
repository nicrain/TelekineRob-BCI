"""TcpFileAdapter — replay recorded TCP data files at original speed.

File format::

    <unix_timestamp> SOD<payload>EOD
    <unix_timestamp> SOD<payload>EOD
    ...

Lines without a valid ``SOD…EOD`` body are silently skipped.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from thymio_control.adapters.base import BaseAdapter
from thymio_control.contracts import EegFrame


def _parse_sod_packet(packet: str):
    from thymio_control.eeg_control_pipeline import parse_sod_packet  # noqa: PLC0415
    return parse_sod_packet(packet)


class TcpFileAdapter(BaseAdapter):
    """Replay a recorded TCP data file at the original inter-packet timing.

    Parameters
    ----------
    file_path : str
        Path to the replay file.  Relative paths are resolved against the
        repository root, then against ``<repo_root>/records/``.
    """

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path
        self._lines: list = []
        self._index   = 0
        self._last_ts = 0.0
        self._done    = False
        self._load_file()

    # ------------------------------------------------------------------
    # BaseAdapter
    # ------------------------------------------------------------------

    def read_frame(self) -> Optional[EegFrame]:
        if self._done:
            return None

        while self._index < len(self._lines):
            line = self._lines[self._index].strip()
            self._index += 1
            if not line:
                continue

            parts = line.split(" ", 1)
            if len(parts) < 2:
                continue
            try:
                ts = float(parts[0])
            except ValueError:
                continue

            payload = parts[1]
            if "SOD" not in payload or "EOD" not in payload:
                continue

            start = payload.find("SOD")
            end   = payload.find("EOD")
            if start < 0 or end < 0 or end <= start:
                continue

            packet  = payload[start: end + 3]
            metrics = _parse_sod_packet(packet)
            if not metrics:
                continue

            if self._last_ts > 0:
                delay = ts - self._last_ts
                if delay > 0:
                    time.sleep(delay)

            self._last_ts = ts
            return EegFrame(ts=time.time(), source="tcp_file", metrics=metrics)

        self._done = True
        return None

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load_file(self) -> None:
        path = Path(self._file_path).expanduser()
        if not path.is_absolute():
            repo_root = Path(__file__).resolve().parents[3]
            candidate_repo   = (repo_root / path).resolve()
            candidate_record = (repo_root / "records" / path).resolve()
            if candidate_repo.exists():
                path = candidate_repo
            elif candidate_record.exists():
                path = candidate_record
            else:
                raise FileNotFoundError(
                    f"TCP replay file not found: {self._file_path!r} "
                    f"(tried {candidate_repo} and {candidate_record})"
                )
        with open(path, "r", encoding="utf-8") as f:
            self._lines = f.readlines()
