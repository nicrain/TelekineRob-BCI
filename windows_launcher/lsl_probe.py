"""LSL liveness probe for the O2 launcher (P8b → P11).

Runs under the DEVICE's ``python_cmd`` — a venv that has ``pylsl`` — NOT in
the launcher itself, which stays zero-dependency.

P11 (three-state liveness): resolving a stream only proves the BRIDGE is
running, not that the DEVICE is feeding it — a powered-off headset leaves an
empty outlet publishing, which ``resolve_byprop`` happily reports as found
(the false-green bug). So after resolve we open an inlet and try to pull a
sample:

    alive      — stream resolved AND yielded a sample (device actually
                 streaming)
    stalled    — stream resolved but no sample arrived (device off /
                 unplugged while the bridge keeps running)
    not-found  — no stream at all (bridge not running)
    no-pylsl   — pylsl missing under this python
"""
import sys


def probe(source_id: str, timeout: float = 2.0, sample_timeout: float = 1.0) -> str:
    """Return the stream's liveness state (one of the four strings above)."""
    try:
        from pylsl import resolve_byprop, StreamInlet
    except ImportError:
        return "no-pylsl"
    try:
        streams = resolve_byprop("source_id", source_id, timeout=timeout)
    except Exception:
        return "not-found"
    if not streams:
        return "not-found"
    try:
        inlet = StreamInlet(streams[0], max_buflen=1)
        sample = inlet.pull_sample(timeout=sample_timeout)
        # pylsl returns (sample, timestamp) or None on timeout — a sample
        # means the device is genuinely streaming.
        return "alive" if sample is not None else "stalled"
    except Exception:
        return "stalled"


def main() -> int:
    source_id = sys.argv[1] if len(sys.argv) > 1 else ""
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    sample_timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    print(probe(source_id, timeout, sample_timeout))
    return 0


if __name__ == "__main__":
    sys.exit(main())
