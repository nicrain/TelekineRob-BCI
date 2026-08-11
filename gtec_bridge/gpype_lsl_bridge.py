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

Robustness (P10④)
-----------------
A data-flow watchdog notices when the device stops feeding the pipeline
(e.g. after a power cycle) and **rebuilds it from scratch** — g.pype's
pipeline is not reusable after a device drop, so teardown + fresh
BCICore8 + fresh LSL outlet is required, retrying with exponential
backoff until the device is back. The watchdog probe reads a sample back
from the bridge's own LSL outlet (pylsl): no sample for ``STALL_SEC`` →
rebuild. ``test_reconnect.py`` already proved fresh-pipeline reconnects
work in g.pype.

Importable WITHOUT gpype/pylsl (both imported lazily at runtime) so the
watchdog + reconnect controller are unit-testable on macOS.

Usage
-----
    python gtec_bridge/gpype_lsl_bridge.py
    # Press Ctrl+C to stop.
"""

import signal
import sys
import time

STREAM_NAME = "gtec_bci_core4"
STALL_SEC = 5.0          # no sample for this long → rebuild
POLL_SEC = 0.5           # watchdog poll cadence
PROBE_TIMEOUT = 0.1      # LSL pull_sample timeout (non-blocking-ish)
BACKOFF_INITIAL = 1.0    # reconnect retry backoff (seconds), doubling
BACKOFF_MAX = 30.0


class DataWatchdog:
    """Tracks the last moment data flowed; decides when the pipeline stalled.

    Pure (injectable clock) so the stall logic is unit-testable.
    """

    def __init__(self, stall_sec: float = STALL_SEC, now_fn=time.monotonic):
        self.stall_sec = float(stall_sec)
        self._now = now_fn
        self.last_data_ts = self._now()

    def mark_data(self) -> None:
        self.last_data_ts = self._now()

    def stalled(self) -> bool:
        return (self._now() - self.last_data_ts) >= self.stall_sec


class LslWatchdogProbe:
    """Reads a sample back from the bridge's own LSL outlet.

    If the device stops feeding the pipeline, no sample arrives at the
    outlet and :meth:`data_arrived` turns False — that is the stall signal.
    pylsl is imported lazily so this module stays importable on macOS.
    """

    def __init__(self, stream_name: str = STREAM_NAME, timeout: float = PROBE_TIMEOUT):
        self.stream_name = stream_name
        self.timeout = timeout
        self._inlet = None

    def reset(self) -> None:
        """Drop the inlet (after a rebuild the outlet is a new object)."""
        self._inlet = None

    def data_arrived(self) -> bool:
        import pylsl  # lazy: not needed on macOS test hosts

        if self._inlet is None:
            try:
                streams = pylsl.resolve_byprop("name", self.stream_name, timeout=2.0)
                if not streams:
                    return False
                self._inlet = pylsl.StreamInlet(streams[0], max_buflen=1)
            except Exception:
                return False
        try:
            sample, _ = self._inlet.pull_sample(timeout=self.timeout)
            return sample is not None
        except Exception:
            return False


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
        backoff_initial: float = BACKOFF_INITIAL,
        backoff_max: float = BACKOFF_MAX,
        sleep=time.sleep,
        now_fn=time.monotonic,
    ):
        self.api = api
        self.watchdog = DataWatchdog(stall_sec=stall_sec, now_fn=now_fn)
        self._poll_sec = poll_sec
        self._backoff = backoff_initial
        self._backoff_initial = backoff_initial
        self._backoff_max = backoff_max
        self._sleep = sleep

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
                self.watchdog.mark_data()
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
        self.watchdog.mark_data()
        stalls = 0
        while True:
            self._sleep(self._poll_sec)
            if self.api.data_arrived():
                self.watchdog.mark_data()
                continue
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
