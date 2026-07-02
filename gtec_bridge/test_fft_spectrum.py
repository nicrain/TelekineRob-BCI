#!/usr/bin/env python3
"""Real-time FFT spectrum analyser for g.tec BCI Core-4 headset.

Pipeline
--------
BCICore8(4ch) → Bandpass(1-30) → Notch(50)
                    │
                    ├── TimeSeriesScope     (filtered waveforms, 4ch)
                    │
                    └── FFT(250pt, Hamming, 50% overlap)
                          │
                          └── SpectrumScope  (real-time spectrum, 4ch)

Frequency resolution: 1 Hz (250 Hz / 250 samples)
Spectrum updates: every 0.5 s (50% overlap on 1s window)

Usage
-----
    python gtec_bridge/test_fft_spectrum.py
    # Close windows or Ctrl+C to stop.
"""

import signal
import sys
import gpype as gp

FS = 250


def _cleanup(pipeline):
    """Release BLE connection to avoid zombie state."""
    try:
        pipeline.stop()
        print("[INFO] Pipeline stopped (BLE disconnected).")
    except Exception:
        pass


if __name__ == "__main__":
    app = gp.MainApp()
    p = gp.Pipeline()

    # ------------------------------------------------------------------
    # Source
    # ------------------------------------------------------------------
    source = gp.BCICore8(channel_count=4)
    print("[OK] BCICore8(channel_count=4) created")

    # ------------------------------------------------------------------
    # Pre-filter
    # ------------------------------------------------------------------
    bp = gp.Bandpass(f_lo=1, f_hi=30)
    notch = gp.Bandstop(f_lo=48, f_hi=52)

    # ------------------------------------------------------------------
    # FFT — 1s window, 1 Hz resolution
    # ------------------------------------------------------------------
    fft = gp.FFT(
        window_size=FS,
        overlap=0.5,
        window_function="hamming",
    )

    # ------------------------------------------------------------------
    # Scopes
    # ------------------------------------------------------------------
    scope_raw = gp.TimeSeriesScope(amplitude_limit=100, time_window=10)
    scope_spec = gp.SpectrumScope(amplitude_limit=5000, num_averages=10)

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------
    p.connect(source, bp)
    p.connect(bp, notch)

    p.connect(notch, fft)
    p.connect(notch, scope_raw)
    p.connect(fft, scope_spec)

    app.add_widget(scope_raw)
    app.add_widget(scope_spec)

    print("[INFO] Two windows:")
    print("       1. TimeSeriesScope — filtered EEG waveforms (4ch)")
    print("       2. SpectrumScope   — real-time FFT spectrum (4ch)")
    print("[INFO] SpectrumScope:")
    print("       X-axis: 0–125 Hz")
    print("       Look for alpha peak (8-12 Hz) — should rise with eyes closed")
    print("[INFO] Close windows or Ctrl+C to stop.\n")

    signal.signal(signal.SIGINT, lambda sig, frame: (_cleanup(p), sys.exit(0)))

    try:
        p.start()
        app.run()
    finally:
        _cleanup(p)

    print("[INFO] Test completed.")
