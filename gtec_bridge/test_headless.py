#!/usr/bin/env python3
"""Test 1: Headless mode — run BCICore8 pipeline without GUI.

Verifies that g.pype Pipeline can acquire data without MainApp.
This is the core requirement for the bridge script.

Usage
-----
    python test_headless.py
"""

import time
import gpype as gp

if __name__ == "__main__":
    p = gp.Pipeline()

    source = gp.BCICore8(channel_count=4)
    print(f"[OK] BCICore8 source created (channel_count=4)")

    # Count how many non-zero channels we see
    # Use CsvWriter as a data tap — it writes to file without GUI
    writer = gp.CsvWriter(file_name="test_headless_output.csv")
    p.connect(source, writer)

    print("[INFO] Starting pipeline (headless, no GUI window)...")
    p.start()

    # Run for 10 seconds, collecting data in background
    print("[INFO] Recording 10 seconds of data...")
    time.sleep(10)

    p.stop()
    print(f"[OK] Pipeline stopped.")
    print(f"[OK] Data saved to test_headless_output.csv")
    print(f"[INFO] Check the CSV file to verify channel count and sample rate.")
