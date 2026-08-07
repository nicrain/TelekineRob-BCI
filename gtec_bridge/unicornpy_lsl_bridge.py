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

Robustness
----------
- ``GetData`` may return 0 scans on a poll (the API allows it). The loop
  then *skips* the round instead of re-pushing the previous round's buffer,
  which would alias stale samples into the control loop. The outlet only
  ever sees new data.
- A ``DeviceException`` (e.g. buffer overflow) no longer kills the bridge:
  the loop stops acquisition, reconnects with exponential backoff, and
  resumes streaming. First connect still fails fast with a troubleshooting
  checklist.

Usage
-----
    python gtec_bridge/unicornpy_lsl_bridge.py
    # Press Ctrl+C to stop.
"""

import signal
import sys
import time

import numpy as np
import UnicornPy
from pylsl import StreamInfo, StreamOutlet

STREAM_NAME = "gtec_hybrid_black"
SAMPLING_RATE = UnicornPy.SamplingRate  # 250 Hz
SAMPLE_BYTES = 4  # float32
FRAME_LENGTH = 1  # sample-by-sample

# Reconnect backoff (seconds), doubling up to a cap.
BACKOFF_INITIAL = 1.0
BACKOFF_MAX = 30.0


def _cleanup(device):
    """Stop acquisition and disconnect cleanly (idempotent)."""
    if device is None:
        return
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


def _connect_unicorn():
    """Discover the paired device and return an opened Unicorn handle.

    Raises on no device found or connect failure — the caller applies
    backoff and retries (only after an initial fast-fail connect).
    """
    devices = UnicornPy.GetAvailableDevices(True)
    if not devices:
        raise RuntimeError("no paired Unicorn Hybrid Black found in Bluetooth cache")
    serial = devices[0]
    print(f"[INFO] Paired device found in Bluetooth cache: {serial}")
    return UnicornPy.Unicorn(serial)


def main() -> int:
    # --- LSL outlet (EEG channels only, ch0-7) ---
    # Use STREAM_NAME as source_id so the WSL2 side can resolve this stream
    # via lsl_source_id="gtec_hybrid_black" (matching buildPatch() and gpype
    # convention where LSLSender uses stream_name as source_id).
    # Device serial (logged above) uniquely identifies the physical unit.
    #
    # TODO(multi-device): when supporting multiple Hybrid Blacks
    # simultaneously, source_id must be unique per-device (e.g. the
    # serial_number).  WSL2 would then need per-device lsl_source_id
    # config entries rather than a single fixed string.
    info = StreamInfo(
        STREAM_NAME,
        "EEG",
        channel_count=UnicornPy.EEGChannelsCount,
        nominal_srate=SAMPLING_RATE,
        channel_format="float32",
        source_id=STREAM_NAME,
    )
    # Write channel labels so RawLslAdapter can resolve the best blink
    # channel (Fp1/Fp2) without hardcoding device-specific indices.
    info.desc().append_child_value(
        "channel_labels", "Fz,C3,Cz,C4,Pz,PO7,Oz,PO8"
    )
    outlet = StreamOutlet(info)
    print(
        f"[INFO] LSL stream: {STREAM_NAME} "
        f"({UnicornPy.EEGChannelsCount} EEG ch @ {SAMPLING_RATE} Hz)"
    )

    # Mutable holder so the SIGINT handler always cleans the *current*
    # device, including one created by a reconnect.
    state = {"device": None}
    signal.signal(
        signal.SIGINT,
        lambda sig, frame: (_cleanup(state["device"]), sys.exit(0)),
    )

    # --- Initial connect: fail fast with a troubleshooting checklist ---
    try:
        device = _connect_unicorn()
    except Exception as exc:
        print(f"[ERROR] Failed to connect: {exc}")
        print("        Check that:")
        print("        1. The headset is turned ON (switch on the back)")
        print("        2. The headset is within Bluetooth range")
        print("        3. No other application is using the device")
        print("        4. The device is paired (Bluetooth cache)")
        return 1

    serial_number = device.GetDeviceInformation().Serial
    n_channels = device.GetNumberOfAcquiredChannels()
    buf = bytearray(FRAME_LENGTH * n_channels * SAMPLE_BYTES)
    print(f"[OK] Connected. Serial={serial_number}, channels={n_channels}")

    state["device"] = device
    backoff = BACKOFF_INITIAL

    try:
        while True:
            # --- Acquire until a DeviceException, then reconnect ---
            try:
                device.StartAcquisition(False)  # False = real EEG
                print("[INFO] Streaming to LSL... Press Ctrl+C to stop.\n")
                while True:
                    n_scans = device.GetData(FRAME_LENGTH, buf, len(buf))
                    if n_scans <= 0:
                        # API allows empty polls. Re-pushing the previous
                        # round's buffer would alias stale samples into the
                        # control loop — skip; only new data reaches the
                        # outlet.
                        continue
                    data = np.frombuffer(buf, dtype=np.float32, count=n_channels)
                    outlet.push_sample(data[0:UnicornPy.EEGChannelsCount])
            except UnicornPy.DeviceException as exc:
                _cleanup(device)
                state["device"] = None
                print(f"[WARN] DeviceException: {exc}")

            # --- Reconnect with backoff until success ---
            while True:
                try:
                    device = _connect_unicorn()
                    break
                except Exception as exc:
                    print(f"[WARN] Connect failed: {exc} — retry in {backoff:.0f}s")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, BACKOFF_MAX)
            backoff = BACKOFF_INITIAL
            state["device"] = device
            print("[OK] Reconnected. Resuming acquisition.")
    except KeyboardInterrupt:
        pass
    finally:
        _cleanup(state["device"])

    print("[INFO] Bridge stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
