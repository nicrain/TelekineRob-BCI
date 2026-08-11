"""LSL liveness probe for the O2 launcher (P8b → P11 → P13).

Runs under the DEVICE's ``python_cmd`` — a venv that has ``pylsl`` — NOT in
the launcher itself, which stays zero-dependency.

P11 (three-state liveness): resolving a stream only proves the BRIDGE is
running, not that the DEVICE is feeding it — a powered-off headset leaves an
empty outlet publishing, which ``resolve_byprop`` happily reports as found.
So after resolve we open an inlet and try to pull a sample.

P13 (sample freshness): pulling ANY sample is still not enough — the outlet
caches the last samples from before a power-off, so an old cached sample
would count as alive. Only a FRESH sample (``local_clock() - timestamp <=
freshness_sec``, default 3 s) proves the device is genuinely streaming.

    alive      — stream resolved AND yielded a FRESH sample
    stalled    — stream resolved but no / only STALE samples
    not-found  — no stream at all (bridge not running)
    no-pylsl   — pylsl missing under this python
"""
import sys


def probe(source_id: str, timeout: float = 2.0, sample_timeout: float = 1.0,
          freshness_sec: float = 3.0) -> str:
    """Return the stream's liveness state (one of the four strings above)."""
    try:
        from pylsl import resolve_byprop, StreamInlet, local_clock
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
    except Exception:
        return "stalled"
    if sample is None:
        return "stalled"
    _, timestamp = sample
    # P13: a cached sample from before a power-off is OLD — a sample older
    # than freshness_sec does not prove the device is streaming.
    if local_clock() - timestamp > freshness_sec:
        return "stalled"
    return "alive"


def main() -> int:
    source_id = sys.argv[1] if len(sys.argv) > 1 else ""
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    sample_timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    freshness_sec = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
    print(probe(source_id, timeout, sample_timeout, freshness_sec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
