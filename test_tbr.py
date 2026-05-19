#!/usr/bin/env python3
"""3-min theta_beta stats for TBR calibration."""
import sys, math
sys.path.insert(0, '/root/ros_thymio')
from thymio_control.adapters.edf_file import EdfFileAdapter
from thymio_control.processors.enrich import enrich_features

adapter = EdfFileAdapter('/root/ros_thymio/records/20260408111446_Patient01.edf', realtime=False)
vals = []; n = 0
while n < 360:
    f = adapter.read_frame()
    if f is None: continue
    feats = enrich_features(f.metrics)
    vals.append(feats["theta_beta"])
    n += 1

sv = sorted(vals)
mean = sum(vals)/len(vals)
std = math.sqrt(sum((v-mean)**2 for v in vals)/len(vals))
print(f"n={len(vals)}  min={min(vals):.4f}  max={max(vals):.4f}  mean={mean:.4f}  std={std:.4f}")
for p in [5,10,25,50,75,90,95]:
    print(f"  p{p:>2}: {sv[int(len(sv)*p/100)]:.4f}")
