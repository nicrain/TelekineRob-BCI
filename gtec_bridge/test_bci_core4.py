#!/usr/bin/env python3
"""Quick connectivity test for g.tec BCI Core-4 headset using g.pype SDK.

Run this script on **Windows** (not WSL) with the BCI Core-4 headset
connected via Bluetooth/dongle.

Usage
-----
    pip install gpype
    python test_bci_core4.py

Expected outcome
----------------
- A TimeSeriesScope window opens showing 4-channel EEG data.
- Close the window to stop.
"""

import gpype as gp

if __name__ == "__main__":
    # ------------------------------------------------------------------
    # MainApp MUST come first — it initialises Qt before any widget
    # ------------------------------------------------------------------
    app = gp.MainApp()
    p = gp.Pipeline()

    # ------------------------------------------------------------------
    # Try source classes known to exist in g.pype SDK
    # BCI Core-4 may be handled by BCICore8 (auto-detecting 4 channels)
    # ------------------------------------------------------------------
    source = None
    source_name = ""

    for cls_name, cls_factory in [
        ("BCICore8", lambda: gp.BCICore8(channel_count=4)),
        ("HybridBlack", lambda: gp.HybridBlack(channel_count=4)),
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
        exit(1)

    # ------------------------------------------------------------------
    # Basic signal chain: source → bandpass → notch(50Hz) → scope
    # ------------------------------------------------------------------
    bandpass = gp.Bandpass(f_lo=1, f_hi=30)
    notch50 = gp.Bandstop(f_lo=48, f_hi=52)

    scope = gp.TimeSeriesScope(amplitude_limit=50, time_window=5)

    p.connect(source, bandpass)
    p.connect(bandpass, notch50)
    p.connect(notch50, scope)

    app.add_widget(scope)

    print(f"\n[INFO] Source class : {source_name}")
    print(f"[INFO] Pipeline started — you should see EEG waveforms.")
    print(f"[INFO] Close the scope window to stop.\n")

    p.start()
    app.run()
    p.stop()

    print("[INFO] Test completed.")
