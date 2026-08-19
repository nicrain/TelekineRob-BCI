#!/usr/bin/env python3
"""P47 (minimal): verify the up-metric baseline floor on the real archive.

The floor is ``baseline = max(rolling median, p50)`` for UP metrics only
(alpha/tbr; ei untouched). This replays the real MetricBlinkDetector over each
alpha/tbr steering session and reports, for floor = the session's rest p50:

- decision_changes: fires the floor removes or adds vs the unclamped replay
  (a config that never binds shows ~0 — the 'not identity' check);
- true_kept / false_blocked: per the protocol ground truth (per trial
  needed=(recorded start == target ? 0 : 1); the first ``needed`` direction-
  switch events are TRUE intended blinks, any beyond are FALSE passive-blink
  misdetections — NOT the old is_blink detector, so no circularity). A floor
  config PRESERVES an event when a fire still occurs within a few frames of
  it, BLOCKS it otherwise.

CLI::

    python thymio_control/scripts/verify_blink_clamp.py --data-dir <archive>
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thymio_control.processors.blink_metric import MetricBlinkDetector  # noqa: E402

# alpha/tbr steering sessions only (ei is out of scope for the floor).
SESSIONS: dict[str, list[str]] = {
    "tbr": [
        "W_s13_tbr_single_2026-08-18_1787071143",
        "W_s2_tbr_single_2026-08-17_1786978657",
        "W_s8_tbr_single_2026-08-18_1787042889",
    ],
    "alpha": [
        "W_s1_alpha_single_2026-08-17_1786963963",
        "W_s7_alpha_single_2026-08-18_1787041241",
    ],
}

MATCH_FRAMES = 3   # a fire within ±N frames of an event counts as preserved


def _metric_value(a: float, t: float, b: float, metric: str) -> float:
    return a if metric == "alpha" else t / (b + 1e-9)


def _load(session_dir: Path, metric: str):
    """(trials, stream, rest_p50) — trials carry protocol + recorded toggles."""
    trials: list[dict] = []
    stream: list[float] = []
    rest: list[float] = []
    for f in sorted(session_dir.iterdir()):
        if not (f.name.startswith("run_") and f.name.endswith(".csv")):
            continue
        with open(f, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            continue
        dirs = [r.get("steer_direction", "").strip() for r in rows]
        start = dirs[0] if dirs and dirs[0] else ""
        target = rows[0].get("b_direction", "").strip()
        state = rows[0].get("b_state", "").strip()
        trials.append({
            "needed": 0 if start == target else 1,
            "fires": [len(stream) + i for i in range(1, len(dirs))
                      if dirs[i] and dirs[i - 1] and dirs[i] != dirs[i - 1]],
            "n": len(rows),
        })
        for r in rows:
            v = _metric_value(float(r["alpha"]), float(r["theta"]), float(r["beta"]), metric)
            stream.append(v)
            if state == "rest":
                rest.append(v)
    s = sorted(rest)
    return trials, stream, (s[len(s) // 2] if s else 0.0)


def _fires(stream: list[float], floor: float | None) -> list[int]:
    """Replay the real UP-mode detector over the stream; fire frame indices."""
    det = MetricBlinkDetector(mode="up", confirm_frames=2, holdoff_frames=4,
                              min_samples=15, clamp_ref=floor)
    return [i for i, v in enumerate(stream) if det.update(v)]


def _evaluate(trials: list[dict], stream: list[float], floor: float | None) -> dict:
    unc, clp = set(_fires(stream, None)), set(_fires(stream, floor))
    dc = len(unc.symmetric_difference(clp))
    true_total = false_total = true_kept = false_blocked = 0
    ptr = 0
    for t in trials:
        for k, f in enumerate(t["fires"]):
            preserved = any(abs(f - g) <= MATCH_FRAMES for g in clp)
            if k < t["needed"]:
                true_total += 1
                true_kept += preserved
            else:
                false_total += 1
                false_blocked += (not preserved)
        ptr += t["n"]
    return {"decision_changes": dc, "true_kept": true_kept, "true_total": true_total,
            "false_blocked": false_blocked, "false_total": false_total}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P47: verify the up-metric baseline floor on archive replay.")
    ap.add_argument("--data-dir", default="experiment_data/archive")
    args = ap.parse_args(argv)
    data_dir = Path(args.data_dir)
    for metric, sids in SESSIONS.items():
        agg = {"decision_changes": 0, "true_kept": 0, "true_total": 0,
               "false_blocked": 0, "false_total": 0}
        for sid in sids:
            sd = data_dir / sid
            if not sd.is_dir():
                continue
            trials, stream, p50 = _load(sd, metric)
            r = _evaluate(trials, stream, p50)   # the floor config under test
            for k in agg:
                agg[k] += r[k]
        print(f"{metric:5s} floor=p50 -> decision_changes={agg['decision_changes']} "
              f"true_kept={agg['true_kept']}/{agg['true_total']} "
              f"false_blocked={agg['false_blocked']}/{agg['false_total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
