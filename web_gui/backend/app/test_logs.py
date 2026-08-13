"""P17①: RingBufferHandler + WSL log-file tailing (log panel)."""
import logging

import pytest

from app import logs


def _logger(name: str, ring: logging.Handler) -> logging.Logger:
    lg = logging.getLogger(name)
    lg.handlers = []
    lg.propagate = False
    lg.setLevel(logging.INFO)
    lg.addHandler(ring)
    return lg


def test_ring_buffer_captures_formatted_records():
    ring = logs.RingBufferHandler(maxlen=10)
    _logger("test_p17", ring).info("hello p17")
    tail = ring.tail()
    assert len(tail) == 1
    assert tail[0]["level"] == "INFO"
    assert tail[0]["logger"] == "test_p17"
    assert tail[0]["message"] == "INFO | test_p17 | hello p17"
    assert tail[0]["ts"] > 0


def test_ring_buffer_is_bounded_to_maxlen():
    ring = logs.RingBufferHandler(maxlen=3)
    lg = _logger("test_p17b", ring)
    for i in range(5):
        lg.info("msg %d", i)
    assert [r["message"] for r in ring.tail()] == [
        "INFO | test_p17b | msg 2",
        "INFO | test_p17b | msg 3",
        "INFO | test_p17b | msg 4",
    ]


def test_ring_buffer_tail_limits_lines():
    ring = logs.RingBufferHandler(maxlen=10)
    lg = _logger("test_p17c", ring)
    for i in range(5):
        lg.info("m%d", i)
    assert [r["message"] for r in ring.tail(2)] == ["INFO | test_p17c | m3", "INFO | test_p17c | m4"]


def test_ring_buffer_emit_never_raises(monkeypatch):
    """A record the handler can't format must not break logging."""
    ring = logs.RingBufferHandler(maxlen=3)

    def _bad_format(_record):
        raise RuntimeError("boom")

    monkeypatch.setattr(ring, "format", _bad_format)
    ring.emit(logging.LogRecord("x", logging.INFO, "", 0, "boom %s", ("y",), None))
    assert ring.tail() == []


def test_tail_files_ignores_missing(monkeypatch):
    monkeypatch.setattr(logs, "_WSL_LOG_FILES", ("/nonexistent/backend.log",))
    assert logs.tail_files() == []


def test_tail_files_reads_last_lines(tmp_path, monkeypatch):
    f = tmp_path / "launcher_backend.log"
    f.write_text("l1\nl2\nl3\n", encoding="utf-8")
    monkeypatch.setattr(logs, "_WSL_LOG_FILES", (str(f),))
    out = logs.tail_files(lines=2)
    assert len(out) == 1
    assert out[0]["source"] == "launcher_backend.log"
    assert out[0]["lines"] == ["l2", "l3"]
