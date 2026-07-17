#!/usr/bin/env python3
"""Headless LSL bridge: stream Unicorn Hybrid Black data to WSL2.

Run this script on **Windows** to send raw 8-channel EEG over LSL.
Requires ``UnicornPy.pyd`` on ``PYTHONPATH`` and ``pylsl``.

On the WSL2 side, the existing ``RawLslAdapter`` picks up the stream
and runs Welch PSD → Policy → /cmd_vel.

Pipeline
--------
UnicornPy(8ch EEG) ──→ pylsl.StreamOutlet
                           │
                  stream: "gtec_hybrid_black"

WSL2 counterpart (in existing launch config):
    RawLslAdapter(source_id="gtec_hybrid_black", timeout=10.0)

Usage
-----
    python gtec_bridge/unicornpy_lsl_bridge.py
    # Press Ctrl+C to stop.
"""

import signal
import sys

import numpy as np
import UnicornPy
from pylsl import StreamInfo, StreamOutlet

STREAM_NAME = "gtec_hybrid_black"
SAMPLING_RATE = UnicornPy.SamplingRate  # 250 Hz


def _cleanup(device):
    """Stop acquisition and disconnect cleanly."""
    try:
        device.StopAcquisition()
        print("[INFO] Acquisition stopped.")
    except Exception:
        pass
    try:
        del device
        print("[INFO] Device disconnected.")
    except Exception:
        pass


if __name__ == "__main__":
    # --- Discover & connect ---
    devices = UnicornPy.GetAvailableDevices(True)
    if not devices:
        print("[ERROR] No paired Unicorn Hybrid Black found.")
        print("        Check that:")
        print("        1. The headset has been paired via Bluetooth at least once")
        print("        2. The Bluetooth adapter (CSR8510 A10) is plugged in")
        sys.exit(1)

    serial = devices[0]
    print(f"[INFO] Paired device found in Bluetooth cache: {serial}")
    print("[INFO] Attempting to connect...")

    try:
        device = UnicornPy.Unicorn(serial)
    except Exception as exc:
        print(f"[ERROR] Failed to connect to {serial}: {exc}")
        print("        Check that:")
        print("        1. The headset is turned ON (switch on the back)")
        print("        2. The headset is within Bluetooth range")
        print("        3. No other application is using the device")
        sys.exit(1)

    serial_number = device.GetDeviceInformation().Serial
    n_channels = device.GetNumberOfAcquiredChannels()
    print(f"[OK] Connected. Serial={serial_number}, channels={n_channels}")

    # --- Pre-allocate buffer (reuse across loop) ---
    FrameLength = 1  # sample-by-sample
    buf = bytearray(FrameLength * n_channels * 4)  # scans × channels × sizeof(float32)

    # --- LSL outlet (EEG channels only, ch0-7) ---
    # Use STREAM_NAME as source_id so the WSL2 side can resolve this stream
    # via lsl_source_id="gtec_hybrid_black" (matching buildPatch() and gpype
    # convention where LSLSender uses stream_name as source_id).
    # Device serial (logged above) uniquely identifies the physical unit.
    info = StreamInfo(
        STREAM_NAME,
        "EEG",
        channel_count=UnicornPy.EEGChannelsCount,
        nominal_srate=SAMPLING_RATE,
        channel_format="float32",
        source_id=STREAM_NAME,
    )
    outlet = StreamOutlet(info)
    print(
        f"[INFO] LSL stream: {STREAM_NAME} "
        f"({UnicornPy.EEGChannelsCount} EEG ch @ {SAMPLING_RATE} Hz)"
    )

    # --- Start acquisition ---
    device.StartAcquisition(False)  # False = real EEG
    print("[INFO] Streaming to LSL... Press Ctrl+C to stop.\n")

    signal.signal(signal.SIGINT, lambda sig, frame: (_cleanup(device), sys.exit(0)))

    try:
        while True:
            device.GetData(FrameLength, buf, len(buf))
            data = np.frombuffer(buf, dtype=np.float32, count=n_channels)
            outlet.push_sample(data[0:UnicornPy.EEGChannelsCount])
    except KeyboardInterrupt:
        pass
    finally:
        _cleanup(device)

    print("[INFO] Bridge stopped.")
