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

Usage
-----
    python gtec_bridge/gpype_lsl_bridge.py
    # Press Ctrl+C to stop.
"""

import signal
import sys
import time
import gpype as gp


def _cleanup(pipeline):
    """Release BLE connection to avoid zombie state."""
    try:
        pipeline.stop()
        print("[INFO] Pipeline stopped (BLE disconnected).")
    except Exception:
        pass


if __name__ == "__main__":
    p = gp.Pipeline()

    # ------------------------------------------------------------------
    # Source
    # ------------------------------------------------------------------
    try:
        source = gp.BCICore8(channel_count=4)
    except Exception as exc:
        print(f"[ERROR] Failed to create BCICore8 source: {exc}")
        print("        Check that:")
        print("        1. The BCI Core-4 headset is turned ON")
        print("        2. The Bluetooth dongle is plugged in")
        print("        3. g.pype SDK is installed: pip install gpype")
        sys.exit(1)
    print("[OK] BCICore8 source configured (channel_count=4)")

    # ------------------------------------------------------------------
    # Minimal pre-filter: remove DC drift + mains hum only.
    # No band-power extraction — that runs in WSL2 via Welch PSD.
    # ------------------------------------------------------------------
    bp = gp.Bandpass(f_lo=0.5, f_hi=45)
    notch = gp.Bandstop(f_lo=48, f_hi=52)

    # ------------------------------------------------------------------
    # LSL sender — discoverable from WSL2
    # ------------------------------------------------------------------
    lsl = gp.LSLSender(stream_name="gtec_bci_core4")

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------
    p.connect(source, bp)
    p.connect(bp, notch)
    p.connect(notch, lsl)

    print("[INFO] LSL stream: gtec_bci_core4")
    print("[INFO] Starting pipeline — connecting to device...\n")

    signal.signal(signal.SIGINT, lambda sig, frame: (_cleanup(p), sys.exit(0)))

    try:
        p.start()
        print("[OK] Pipeline started. Streaming to LSL... Press Ctrl+C to stop.\n")
        # Block until Ctrl+C (signal.pause() is Unix-only)
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"[ERROR] Pipeline failed to start: {exc}")
        print("        Check that:")
        print("        1. The BCI Core-4 headset is turned ON and in range")
        print("        2. No other application is using the device")
        sys.exit(1)
    finally:
        _cleanup(p)

    print("[INFO] Bridge stopped.")
