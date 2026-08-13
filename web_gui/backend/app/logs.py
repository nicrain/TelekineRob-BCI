"""Recent-log ring buffer + WSL log-file tailing (P17① log panel).

``RingBufferHandler`` captures the last N log records in memory so the web
GUI can show "recent backend/bridge log" without reading files; ``tail_files``
best-effort reads the known WSL-side launcher logs (/tmp/launcher_*.log) when
the backend was started by the O2 launcher.
"""

from __future__ import annotations

import logging
from collections import deque
from pathlib import Path

MAX_RECORDS = 500
DEFAULT_TAIL_LINES = 100

# WSL-side logs written by the O2 launcher (only when it started the backend).
_WSL_LOG_FILES = ("/tmp/launcher_backend.log", "/tmp/launcher_frontend.log")


class RingBufferHandler(logging.Handler):
    """Keeps the last ``maxlen`` formatted log records (thread-safe deque)."""

    def __init__(self, maxlen: int = MAX_RECORDS) -> None:
        super().__init__()
        self._records: deque[dict] = deque(maxlen=maxlen)
        self.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._records.append(
                {
                    "ts": round(record.created, 3),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": self.format(record),
                }
            )
        except Exception:  # never let the handler break logging
            pass

    def tail(self, lines: int = DEFAULT_TAIL_LINES) -> list[dict]:
        return list(self._records)[-lines:]


def tail_files(lines: int = DEFAULT_TAIL_LINES) -> list[dict]:
    """Best-effort tail of the known WSL launcher logs; empty when absent."""
    out: list[dict] = []
    for path_str in _WSL_LOG_FILES:
        path = Path(path_str)
        try:
            if not path.exists():
                continue
            tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
        except OSError:
            continue
        out.append({"source": path.name, "path": str(path), "lines": tail})
    return out
