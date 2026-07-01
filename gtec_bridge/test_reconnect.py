#!/usr/bin/env python3
"""Test whether g.pype can handle device reconnection without manual re-pairing.

Scenario
--------
1. Connect to BCI Core-4, stream 10 seconds → scope visible
2. p.stop()  (disconnect)
3. Wait 3 seconds
4. New pipeline + new BCICore8 → start() (reconnect)
5. Stream another 10 seconds

If round 3 shows EEG → reconnection works in g.pype.
If round 3 is blank → problem is deeper (gtec_ble / Windows BLE stack).

Usage
-----
    python gtec_bridge/test_reconnect.py
"""

import signal
import sys
import time
import gpype as gp


def _cleanup(pipeline):
    try:
        pipeline.stop()
        print("[INFO] Pipeline stopped (BLE disconnected).")
    except Exception:
        pass

if __name__ == "__main__":
    app = gp.MainApp()
    p = gp.Pipeline()

    source = gp.BCICore8(channel_count=4)
    scope = gp.TimeSeriesScope(amplitude_limit=50, time_window=5)

    p.connect(source, scope)
    app.add_widget(scope)

    signal.signal(signal.SIGINT, lambda sig, frame: (_cleanup(p), sys.exit(0)))

    try:
        # --------------------------------------------------------------
        # Round 1: initial connection
        # --------------------------------------------------------------
        print("[1] Starting first connection...")
        p.start()
        print("[1] Running 10 seconds — confirm you see EEG waveforms.")
        print("[1] (if scope is blank, the initial connection failed)")
        time.sleep(10)
    finally:
        _cleanup(p)

    # ------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------
    print("[2] Pipeline stopped. Waiting 3 seconds...")
    time.sleep(3)

    # ------------------------------------------------------------------
    # Round 2: reconnect WITHOUT touching Windows Bluetooth settings
    # ------------------------------------------------------------------
    print("[3] Starting SECOND connection (reconnect test)...")
    print("[3] DO NOT touch Windows Bluetooth settings.")
    print("[3] If you see EEG again → reconnection works in g.pype.")
    print("[3] If scope is blank → reconnection fails, problem is deeper.")

    # Re-build pipeline from scratch (fresh BCICore8 instance)
    p2 = gp.Pipeline()
    source2 = gp.BCICore8(channel_count=4)
    scope2 = gp.TimeSeriesScope(amplitude_limit=50, time_window=5)

    p2.connect(source2, scope2)
    app.add_widget(scope2)

    signal.signal(signal.SIGINT, lambda sig, frame: (_cleanup(p2), sys.exit(0)))

    try:
        p2.start()
        print("[3] Running 10 seconds — check the NEW scope window...")
        time.sleep(10)
    finally:
        _cleanup(p2)

    print("[4] Test finished.")
    print("[4] If round 3 showed EEG → g.pype reconnection works fine.")
    print("[4] If round 3 was blank → problem confirmed, need to dig deeper.")
