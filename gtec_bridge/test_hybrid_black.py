#!/usr/bin/env python3
"""Quick connectivity test for g.tec Unicorn Hybrid Black using gpype SDK.

Run this script on **Windows** (not WSL) with the Hybrid Black
connected via Bluetooth dongle.

Usage
-----
    pip install gpype
    python gtec_bridge/test_hybrid_black.py

Expected outcome
----------------
- A TimeSeriesScope window opens showing 8-channel EEG data.
- Close the window to stop.
"""

import signal
import sys
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

    # ------------------------------------------------------------------
    # Try HybridBlack first, fall back to BCICore8
    # ------------------------------------------------------------------
    source = None
    source_name = ""

    for cls_name, cls_factory in [
        ("HybridBlack", lambda: gp.HybridBlack(channel_count=8)),
        ("BCICore8", lambda: gp.BCICore8(channel_count=8)),
    ]:
        try:
            source = cls_factory()
            source_name = cls_name
            print(f"[OK]  {cls_name} source created successfully")
            break
        except Exception as exc:
            print(f"[FAIL] {cls_name}: {exc}")

    if source is None:
        print("\n[ERROR] No g.tec device source could be created.")
        print("        Check that:")
        print("        1. The headset is turned on and paired via Bluetooth")
        print("        2. g.pype SDK is installed: pip install gpype")
        print("        3. No other application is using the device")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Signal chain: source → bandpass → notch(50Hz) → scope
    # ------------------------------------------------------------------
    bandpass = gp.Bandpass(f_lo=1, f_hi=30)
    notch50 = gp.Bandstop(f_lo=48, f_hi=52)

    scope = gp.TimeSeriesScope(amplitude_limit=50, time_window=5)

    p.connect(source, bandpass)
    p.connect(bandpass, notch50)
    p.connect(notch50, scope)

    app.add_widget(scope)

    print(f"\n[INFO] Source class : {source_name}")
    print(f"[INFO] Pipeline started — you should see 8-channel EEG waveforms.")
    print(f"[INFO] Close the scope window to stop, or Ctrl+C.\n")

    signal.signal(signal.SIGINT, lambda sig, frame: (_cleanup(p), sys.exit(0)))

    try:
        p.start()
        app.run()
    finally:
        _cleanup(p)

    print("[INFO] Test completed.")
