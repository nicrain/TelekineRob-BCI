#!/usr/bin/env python3
"""Headless LSL bridge: stream g.tec BCI Core-4 data to WSL2.

Run this script on **Windows** to send raw EEG over LSL.
On the WSL2 side, the existing ``RawLslAdapter`` picks up the stream
and runs Welch PSD → Policy → /cmd_vel.

Pipeline
--------
BCICore8(4ch) → Bandpass(0.5-45Hz) → Notch(50Hz) → LSLSender
                                                      │
                                            stream: "gtec_bci_core4"

WSL2 counterpart (in existing launch config):
    RawLslAdapter(source_id="gtec_bci_core4", timeout=10.0)

Robustness (P10④ + P12)
------------------------
P10: a data-flow watchdog notices when the device stops feeding the
    pipeline and rebuilds it from scratch (g.pype's pipeline is not reusable
    after a device drop): teardown + fresh BCICore8 + fresh LSL outlet,
    retrying with exponential backoff until the device is back. The watchdog
    probe reads a sample back from the bridge's own LSL outlet (pylsl).
    ``test_reconnect.py`` already proved fresh-pipeline reconnects work.

P12: watchdog false-positive fixes (real-device churn — a "Reconnected →
    Pipeline stopped → No amplifiers connected" loop while the device is
    healthy, caused by rapid rebuilds leaving several same-name outlets and
    the probe latching onto a stale empty one):
      ① ``GRACE_SEC`` after a (re)build before stall is judged — outlet
        discovery + probe latch take a moment;
      ② the probe scans candidates for one that actually yields a sample
        instead of locking to ``resolve_byprop``'s streams[0], and drops /
        re-resolves an inlet that stays empty;
      ③ a stall is only judged after data was actually seen — a fresh
        pipeline that never produced a sample is never torn down (initial
        connect stays fail-fast via build/start exceptions);
      ④ ``STALL_SEC`` raised 5 s → 10 s to tolerate normal gaps.
    Principle: rather miss a stall and wait one more round than tear down a
    healthy pipeline.

Importable WITHOUT gpype/pylsl (both imported lazily at runtime) so the
watchdog, controller and probe are unit-testable on macOS.

Usage
-----
    python gtec_bridge/gpype_lsl_bridge.py
    # Press Ctrl+C to stop.
"""

import signal
import sys
import time

STREAM_NAME = "gtec_bci_core4"
STALL_SEC = 10.0         # no sample for this long (after data was seen) → rebuild
GRACE_SEC = 10.0         # after a (re)build, do not judge stall for this long
POLL_SEC = 0.5           # watchdog poll cadence
PROBE_TIMEOUT = 0.1      # LSL pull_sample timeout (non-blocking-ish)
SCAN_TIMEOUT = 0.05      # per-candidate probe when selecting an alive outlet
EMPTY_RESOLVE_AFTER = 3  # empty reads before dropping + re-resolving the inlet
FRESHNESS_SEC = 3.0      # a sample older than this does NOT prove streaming (P13)
BACKOFF_INITIAL = 1.0    # reconnect retry backoff (seconds), doubling
BACKOFF_MAX = 30.0


class DataWatchdog:
    """Tracks the last moment data flowed; decides when the pipeline stalled.

    P12③: a stall is only judged after data was actually seen — a pipeline
    that never produced a sample is never torn down as "stalled". Pure
    (injectable clock) so the stall logic is unit-testable.
    """

    def __init__(self, stall_sec: float = STALL_SEC, now_fn=time.monotonic):
        self.stall_sec = float(stall_sec)
        self._now = now_fn
        self.seen_data = False
        self.last_data_ts = self._now()

    def reset(self) -> None:
        """Forget prior data after a (re)build — stall is judged per pipeline
        instance, only once THIS instance produced a sample."""
        self.seen_data = False
        self.last_data_ts = self._now()

    def mark_data(self) -> None:
        self.seen_data = True
        self.last_data_ts = self._now()

    def stalled(self) -> bool:
        if not self.seen_data:
            return False
        return (self._now() - self.last_data_ts) >= self.stall_sec


class LslWatchdogProbe:
    """Reads a sample back from the bridge's own LSL outlet.

    P12②: instead of locking to ``resolve_byprop``'s streams[0] (rapid
    rebuilds leave several same-name outlets, the first of which may be a
    stale empty one), scan the candidates and keep one that actually yields
    a sample. If that inlet later goes empty for ``empty_resolve_after``
    reads, drop it and re-resolve rather than locking to a dead outlet.
    pylsl is imported lazily so this module stays importable on macOS.
    """

    def __init__(
        self,
        stream_name: str = STREAM_NAME,
        timeout: float = PROBE_TIMEOUT,
        scan_timeout: float = SCAN_TIMEOUT,
        empty_resolve_after: int = EMPTY_RESOLVE_AFTER,
        freshness_sec: float = FRESHNESS_SEC,
        clock=None,
    ):
        self.stream_name = stream_name
        self.timeout = timeout
        self._scan_timeout = scan_timeout
        self._empty_resolve_after = empty_resolve_after
        self._freshness_sec = float(freshness_sec)
        self._clock = clock  # injectable; None → pylsl.local_clock (lazy)
        self._inlet = None
        self._empty_reads = 0

    def reset(self) -> None:
        """Drop the inlet (after a rebuild the outlet is a new object)."""
        self._inlet = None
        self._empty_reads = 0

    def _now(self) -> float:
        if self._clock is not None:
            return self._clock()
        import pylsl  # lazy
        return pylsl.local_clock()

    def _fresh(self, sample) -> bool:
        # P13②: an outlet caches the last samples from before a power-off —
        # only a sample younger than freshness_sec proves the device is
        # actually streaming right now.
        if sample is None:
            return False
        _, timestamp = sample
        # P18①: pull_sample can return timestamp=None on the stream-interrupt /
        # timeout boundary — ``self._now() - None`` would TypeError and the
        # probe must never crash the bridge. A missing/non-numeric timestamp
        # simply means "not provably fresh" → no data.
        if not isinstance(timestamp, (int, float)):
            return False
        return self._now() - timestamp <= self._freshness_sec

    def data_arrived(self) -> bool:
        import pylsl  # lazy: not needed on macOS test hosts

        if self._inlet is None:
            self._inlet = self._resolve_alive(pylsl)
            if self._inlet is None:
                self._empty_reads += 1
                return False
            self._empty_reads = 0
            return True  # the scan already confirmed a FRESH sample flows
        try:
            sample = self._inlet.pull_sample(timeout=self.timeout)
            fresh = self._fresh(sample)
        except Exception:
            # P18②: any probe failure (incl. a None-timestamp TypeError on the
            # stream boundary) is "no data this round" — keep monitoring, never
            # let the probe crash the bridge.
            fresh = False
        if fresh:
            self._empty_reads = 0
            return True
        self._empty_reads += 1
        if self._empty_reads >= self._empty_resolve_after:
            self._inlet = None  # likely latched a stale outlet — re-resolve
            self._empty_reads = 0
        return False

    def _resolve_alive(self, pylsl):
        """Resolve the stream and return an inlet to a candidate that
        actually yields a FRESH sample (P12② + P13②); None if none does."""
        try:
            streams = pylsl.resolve_byprop("name", self.stream_name, timeout=2.0)
        except Exception:
            return None
        for stream in streams:
            try:
                inlet = pylsl.StreamInlet(stream, max_buflen=1)
                if self._fresh(inlet.pull_sample(timeout=self._scan_timeout)):
                    return inlet
            except Exception:
                continue
        return None


class GpypeBridge:
    """Real gpype access behind the api surface the controller drives.

    ``build()``/``start()`` raise on connect failure — the controller's
    initial connect fails fast (operator-facing checklist), reconnect
    retries with backoff. ``teardown()`` releases the device so a rebuild
    does not hit the classic "device is in use" error.
    """

    def __init__(self, probe=None):
        self.stream_name = STREAM_NAME
        self.pipeline = None
        self.probe = probe or LslWatchdogProbe()

    def build(self) -> None:
        import gpype as gp  # lazy: Windows / g.pype venv only

        pipeline = gp.Pipeline()
        source = gp.BCICore8(channel_count=4)
        bp = gp.Bandpass(f_lo=0.5, f_hi=45)
        notch = gp.Bandstop(f_lo=48, f_hi=52)
        lsl = gp.LSLSender(stream_name=self.stream_name)
        pipeline.connect(source, bp)
        pipeline.connect(bp, notch)
        pipeline.connect(notch, lsl)
        self.pipeline = pipeline
        self.probe.reset()  # new outlet → re-resolve on next check

    def start(self) -> None:
        self.pipeline.start()

    def teardown(self) -> None:
        pipeline, self.pipeline = self.pipeline, None
        if pipeline is not None:
            try:
                pipeline.stop()
                print("[INFO] Pipeline stopped (device released).")
            except Exception:
                pass

    def data_arrived(self) -> bool:
        return self.probe.data_arrived()


class BridgeController:
    """Drives the pipeline lifecycle: monitor → detect stall → rebuild+retry.

    All gpype/pylsl access goes through the injected ``api``, so the
    watchdog and reconnect flow are unit-testable without the SDKs.
    """

    def __init__(
        self,
        api,
        *,
        stall_sec: float = STALL_SEC,
        poll_sec: float = POLL_SEC,
        grace_sec: float = GRACE_SEC,
        backoff_initial: float = BACKOFF_INITIAL,
        backoff_max: float = BACKOFF_MAX,
        sleep=time.sleep,
        now_fn=time.monotonic,
    ):
        self.api = api
        self.watchdog = DataWatchdog(stall_sec=stall_sec, now_fn=now_fn)
        self._poll_sec = poll_sec
        self._grace_sec = float(grace_sec)
        self._now = now_fn
        self._backoff = backoff_initial
        self._backoff_initial = backoff_initial
        self._backoff_max = backoff_max
        self._sleep = sleep
        self._grace_until = 0.0

    def _reconnect_once(self, max_attempts=None) -> bool:
        """Teardown, then build+start with exponential backoff.

        Returns True once the pipeline is running again; False only when
        ``max_attempts`` (test hook) were all exhausted.
        """
        self.api.teardown()
        attempts = 0
        while max_attempts is None or attempts < max_attempts:
            try:
                self.api.build()
                self.api.start()
                self._backoff = self._backoff_initial
                self.watchdog.reset()
                self._grace_until = self._now() + self._grace_sec  # P12①
                print("[OK] Reconnected. Resuming stream.")
                return True
            except Exception as exc:
                attempts += 1
                print(f"[WARN] Rebuild failed: {exc} — retry in {self._backoff:.0f}s")
                self._sleep(self._backoff)
                self._backoff = min(self._backoff * 2, self._backoff_max)
        return False

    def run(self, *, max_stalls=None) -> None:
        """Initial connect fails fast (raises); a later stall triggers a
        rebuild with retry. Returns only after ``max_stalls`` rebuilds
        (test hook) — production runs until Ctrl+C."""
        self.api.build()
        self.api.start()
        self.watchdog.reset()
        self._grace_until = self._now() + self._grace_sec  # P12①
        stalls = 0
        while True:
            self._sleep(self._poll_sec)
            try:
                arrived = self.api.data_arrived()
            except Exception as exc:
                # P18③ backstop: a probe exception must never kill the bridge —
                # treat it as "no data" this round and keep the monitoring loop
                # alive (initial connect still fails fast via build/start).
                print(f"[WARN] probe failed, ignored: {exc}")
                arrived = False
            if arrived:
                self.watchdog.mark_data()
                continue
            if self._now() < self._grace_until:
                continue  # P12①: grace after (re)build — no stall judgement
            if not self.watchdog.stalled():
                continue
            stalls += 1
            if max_stalls is not None and stalls > max_stalls:
                return
            if not self._reconnect_once():
                return


def _cleanup(api):
    try:
        api.teardown()
    except Exception:
        pass


def main() -> int:
    api = GpypeBridge()
    controller = BridgeController(api)
    signal.signal(signal.SIGINT, lambda sig, frame: (_cleanup(api), sys.exit(0)))
    try:
        controller.run()
    except Exception as exc:
        print(f"[ERROR] Failed to connect: {exc}")
        print("        Check that:")
        print("        1. The BCI Core-4 headset is turned ON")
        print("        2. The Bluetooth dongle is plugged in")
        print("        3. g.pype SDK is installed: pip install gpype")
        api.teardown()
        return 1
    finally:
        api.teardown()
    print("[INFO] Bridge stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
