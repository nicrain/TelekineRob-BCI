#!/usr/bin/env python3
"""Test whether g.pype can handle device reconnection without manual re-pairing.

Scenario
--------
1. Connect to BCI Core-4, stream 5 seconds → scope visible
2. p.stop()  (disconnect)
3. Wait 2 seconds
4. p.start() (reconnect) — does it work without Windows re-pairing?
5. Stream another 5 seconds

Usage
-----
    python gtec_bridge/test_reconnect.py
"""

import time
import gpype as gp

if __name__ == "__main__":
    app = gp.MainApp()
    p = gp.Pipeline()

    source = gp.BCICore8(channel_count=4)
    scope = gp.TimeSeriesScope(amplitude_limit=50, time_window=5)

    p.connect(source, scope)
    app.add_widget(scope)

    # ------------------------------------------------------------------
    # Round 1: initial connection
    # ------------------------------------------------------------------
    print("[1] Starting first connection...")
    p.start()
    print("[1] Running 10 seconds — confirm you see EEG waveforms.")
    print("[1] (if scope is blank, the initial connection failed)")
    time.sleep(10)

    # ------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------
    print("[2] Stopping pipeline (disconnecting BLE)...")
    p.stop()
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

    p2.start()
    print("[3] Running 10 seconds — check the NEW scope window...")
    time.sleep(10)

    p2.stop()
    print("[4] Test finished.")
    print("[4] If round 3 showed EEG → g.pype reconnection works fine.")
    print("[4] If round 3 was blank → problem confirmed, need to dig deeper.")
