#!/usr/bin/env python3
"""Verify ThetaBetaPolicy on 30s of EDF (from legacy path)."""
import sys
sys.path.insert(0, '/root/ros_thymio')

from thymio_control.adapters.edf_file import EdfFileAdapter
from thymio_control.processors.enrich import enrich_features

# Use legacy path (what ROS node actually uses)
from thymio_control.eeg_control_pipeline import ThetaBetaPolicy

adapter = EdfFileAdapter('/root/ros_thymio/records/20260408111446_Patient01.edf', realtime=False)
policy = ThetaBetaPolicy()

print(f"{'t(s)':>5} {'θ/β':>8} {'smooth':>8} {'speed':>6} {'steer':>6}")
print("-" * 40)

count = 0
while count < 60:
    f = adapter.read_frame()
    if f is None: continue
    feats = enrich_features(f.metrics)
    intents = policy.compute_intents(feats)
    tbr = feats["theta_beta"]
    smooth = policy._tbr_smooth
    t = count * 0.5
    print(f"{t:>5.1f} {tbr:>8.4f} {smooth:>8.4f} {intents['speed_intent']:>6.3f} {intents['steer_intent']:>6.3f}")
    count += 1
