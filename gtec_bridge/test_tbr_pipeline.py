#!/usr/bin/env python3
"""Build a TBR (theta/beta ratio) processing chain in g.pype.

Pipeline
--------
BCICore8(4ch) ──┬── Bandpass(1-30Hz) ── Notch(50Hz) ── raw ──────────────┐
                 │                                                         │
                 └── Router[ch0=Fz] ──┬── BP(4-8)  ── ² ── MA ── theta ──┤
                                      │                           │        │
                                      └── BP(13-30) ── ² ── MA ── beta ───┤
                                                                  │   │    │
                                                          Eq("a/b") ──┤    │
                                                                 TBR ──────┤
                                                                           │
                                                          Router(merge) ───┤
                                                                           │
                                                          TimeSeriesScope ─┘

Usage
-----
    python gtec_bridge/test_tbr_pipeline.py
    # Close the scope window to stop.
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

FS = 250  # BCI Core sampling rate

if __name__ == "__main__":
    # Qt must come first
    app = gp.MainApp()
    p = gp.Pipeline()

    # ------------------------------------------------------------------
    # Source
    # ------------------------------------------------------------------
    source = gp.BCICore8(channel_count=4)
    print("[OK] BCICore8(channel_count=4) created")

    # ------------------------------------------------------------------
    # Pre-filter (common to all channels)
    # ------------------------------------------------------------------
    bandpass = gp.Bandpass(f_lo=1, f_hi=30)
    notch50 = gp.Bandstop(f_lo=48, f_hi=52)

    # ------------------------------------------------------------------
    # Channel selector: pick Fz (ch0) for TBR computation
    # ------------------------------------------------------------------
    ch_splitter = gp.Router(
        input_channels=gp.Router.ALL,
        output_channels={"all": gp.Router.ALL, "fz": [0]},
    )

    # ------------------------------------------------------------------
    # Theta band (4–8 Hz) power
    # ------------------------------------------------------------------
    theta_bp = gp.Bandpass(f_lo=4, f_hi=8)
    theta_pow = gp.Equation("in**2")
    theta_smooth = gp.MovingAverage(window_size=250)  # 1 s at 250 Hz

    # ------------------------------------------------------------------
    # Beta band (13–30 Hz) power
    # ------------------------------------------------------------------
    beta_bp = gp.Bandpass(f_lo=13, f_hi=30)
    beta_pow = gp.Equation("in**2")
    beta_smooth = gp.MovingAverage(window_size=250)

    # ------------------------------------------------------------------
    # TBR = theta_power / beta_power
    # ------------------------------------------------------------------
    tbr = gp.Equation("a / b")

    # ------------------------------------------------------------------
    # TWO separate scopes — different amplitude scales
    # ------------------------------------------------------------------
    scope_raw = gp.TimeSeriesScope(amplitude_limit=100, time_window=10)
    scope_tbr = gp.TimeSeriesScope(amplitude_limit=3, time_window=10)

    # ==================================================================
    # Connections
    # ==================================================================
    # Source → pre-filter
    p.connect(source, bandpass)
    p.connect(bandpass, notch50)

    # Pre-filter → channel splitter
    p.connect(notch50, ch_splitter)

    # Theta path: Fz → BP(4-8) → ² → smooth → TBR port "a"
    p.connect(ch_splitter["fz"], theta_bp)
    p.connect(theta_bp, theta_pow)
    p.connect(theta_pow, theta_smooth)
    p.connect(theta_smooth, tbr["a"])

    # Beta path: Fz → BP(13-30) → ² → smooth → TBR port "b"
    p.connect(ch_splitter["fz"], beta_bp)
    p.connect(beta_bp, beta_pow)
    p.connect(beta_pow, beta_smooth)
    p.connect(beta_smooth, tbr["b"])

    # Display: raw EEG on one scope, TBR on another
    p.connect(ch_splitter["all"], scope_raw)
    p.connect(tbr, scope_tbr)

    # Also record TBR to CSV
    csv = gp.CsvWriter(file_name="test_tbr_output.csv")
    p.connect(tbr, csv)

    app.add_widget(scope_raw)
    app.add_widget(scope_tbr)

    print("[INFO] Pipeline started. TWO scope windows:")
    print("       Scope 1 (amplitude=100) : filtered raw EEG, 4 channels")
    print("       Scope 2 (amplitude=3)   : TBR = theta/beta ratio")
    print("")
    print("[INFO] Interpreting TBR trace:")
    print("       TBR > 1 → theta dominant → relaxed / drowsy")
    print("       TBR < 1 → beta  dominant → alert / focused")
    print("       Try closing your eyes → TBR should rise")
    print("[INFO] TBR also saved to test_tbr_output.csv")
    print("[INFO] Close scope windows or Ctrl+C to stop.\n")

    signal.signal(signal.SIGINT, lambda sig, frame: (_cleanup(p), sys.exit(0)))

    try:
        p.start()
        app.run()
    finally:
        _cleanup(p)

    print("[INFO] Test completed.")
