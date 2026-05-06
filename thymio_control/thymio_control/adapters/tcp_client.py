"""TcpClientAdapter — connects to an external EEG TCP server (SOD/EOD protocol).

Migrated from ``TcpClientJsonAdapter`` in the monolith.  Maintains a
non-blocking socket with automatic reconnection.  On each ``read_frame``
call it drains the socket buffer, extracts complete ``SOD…EOD`` packets,
and returns only the most recent valid one to minimise latency.
"""
from __future__ import annotations

import logging
import socket
import time
from typing import Optional

from thymio_control.adapters.base import BaseAdapter
from thymio_control.contracts import EegFrame
from thymio_control.processors.tcp_protocol import parse_sod_packet as _parse_sod_packet

_log = logging.getLogger(__name__)


class TcpClientAdapter(BaseAdapter):
    """Connect to an external EEG service via TCP and read SOD/EOD packets.

    Parameters
    ----------
    host : str
        TCP server host.
    port : int
        TCP server port.
    reconnect_sec : float
        Minimum interval between reconnection attempts.
    """

    def __init__(self, host: str, port: int, reconnect_sec: float = 1.0) -> None:
        self._host = host
        self._port = int(port)
        self._reconnect_sec = max(0.1, float(reconnect_sec))
        self._sock: Optional[socket.socket] = None
        self._buf  = ""
        self._last_connect_attempt = 0.0

    # ------------------------------------------------------------------
    # BaseAdapter
    # ------------------------------------------------------------------

    def read_frame(self) -> Optional[EegFrame]:
        self._connect_if_needed()
        if self._sock is None:
            return None
        self._drain_socket()
        packets = self._extract_all_packets()
        if not packets:
            return None

        if len(packets) > 1:
            _log.warning("buffer truncation: discarded %d old packet(s)", len(packets) - 1)

        for packet in reversed(packets):
            metrics = _parse_sod_packet(packet)
            if metrics:
                return EegFrame(ts=time.time(), source="tcp_client", metrics=metrics)
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect_if_needed(self) -> None:
        if self._sock is not None:
            return
        now = time.time()
        if now - self._last_connect_attempt < self._reconnect_sec:
            return
        self._last_connect_attempt = now
        try:
            sock = socket.create_connection((self._host, self._port), timeout=2.0)
            sock.setblocking(False)
            self._sock = sock
            _log.info("connected to %s:%d", self._host, self._port)
        except Exception:
            self._sock = None

    def _close_socket(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None
        self._buf  = ""

    def _drain_socket(self) -> None:
        while True:
            try:
                data = self._sock.recv(4096)  # type: ignore[union-attr]
                if not data:
                    _log.info("disconnected from %s:%d", self._host, self._port)
                    self._close_socket()
                    return
                self._buf += data.decode("utf-8", errors="ignore")
            except BlockingIOError:
                break
            except OSError:
                self._close_socket()
                return

    def _extract_all_packets(self) -> list:
        packets: list = []
        while True:
            start = self._buf.find("SOD")
            if start < 0:
                if len(self._buf) > 65536:
                    self._buf = self._buf[-1024:]
                return packets
            if start > 0:
                self._buf = self._buf[start:]
            end = self._buf.find("EOD", 3)
            if end < 0:
                return packets
            next_sod = self._buf.find("SOD", 3, end)
            if next_sod > 0:
                self._buf = self._buf[next_sod:]
                continue
            packets.append(self._buf[: end + 3])
            self._buf = self._buf[end + 3:]
