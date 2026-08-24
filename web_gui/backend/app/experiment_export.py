"""E5: export experiment_data/<session>/ records into analysis tables.

Reads every session under the experiment data dir (respects
``EXPERIMENT_DATA_DIR``) and writes:

  master_trials.csv       — one row per trial, ALL sessions (long table)
  condition_summary.csv   — one row per (session, channel) discrimination stats

P46 adds the steering direction-control quality metric: ``clean_switch`` per
trial (master table) and ``clean_switch_rate`` / ``avg_toggles_per_switch`` per
(session, run, channel) (summary). A trial's output direction trajectory is
scored by how many times it flips (``toggles``) vs. how many flips the target
requires from the trial's starting direction (``needed``); ``clean`` = they
match. The rate is aggregated over the 'needs switch' trials only (attention
trials whose target changed from the previous attention trial).

P# redefines the SPEED channel hit/FA: it is judged from the ACTUAL forward
command, not the speed_intent classifier — a frame counts as moving when
``cmd_lin > SPEED_CMD_THRESHOLD``, a trial as successful when at least
``MOVING_RATIO_THRESHOLD`` of its speed-role frames are moving. The master
table gains ``mean_cmd_lin`` / ``moving_time_ratio`` / ``speed_active``; the
speed summary hit/FA use ``speed_active`` and its AUC uses the continuous
``mean_cmd_lin``. Steering metrics are untouched.

Pure Python stdlib (the backend venv stays minimal — no pandas), deterministic
(same input → same output), and tolerant (missing/corrupt files → skip or
fall back to ``''``, never crash).

CLI::

    python -m app.experiment_export --out <dir>

The ``master_trials.csv`` column names are aligned with
``experiment.TRIAL_CSV_COLUMNS`` / ``TRIALS_CSV_COLUMNS`` (imported, not
re-invented): ``speed_intent`` is the per-trial mean of the frame column of
the same name (the dispatch's "speed"), ``steer_intent`` / ``steer_direction``
/ ``is_blink`` / ``latency_ms`` likewise, and ``mean_alpha`` / ``mean_tbr`` /
``mean_ei`` / ``blink_count`` come straight from ``trials.csv``.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional

from .experiment import TRIAL_CSV_COLUMNS, TRIALS_CSV_COLUMNS

# ── analysis assumptions (documented; these are analysis choices, tune per
# ── experiment — an attention hit is defined as the channel's mean output
# ── exceeding the threshold) ──────────────────────────────────────────────
# P#: the SPEED channel's hit/FA is judged from the ACTUAL forward command
# (cmd_lin), NOT the speed_intent classifier output — a non-zero speed_intent
# can sit under the old 0.5 threshold while the car is genuinely moving (or
# vice versa). These are real-device verified analysis assumptions:
SPEED_CMD_THRESHOLD = 0.02    # a frame counts as MOVING when cmd_lin > this
                              # (0.02 m/s: verified as the slowest Thymio
                              # observable displacement).
MOVING_RATIO_THRESHOLD = 0.10 # a trial counts as SUCCESSFUL (speed_active)
                              # when at least this fraction of its speed-role
                              # frames are moving (0.10 ≈ 2 s of a 20 s trial).
STEER_HIT_THRESHOLD = 0.5     # mean steer_intent > this → steering attention hit

# master_trials.csv columns: session fields + the run id + the target trio +
# the per-trial outputs (names aligned with the frame / trial-summary CSVs) +
# the clean-switch flag (P46) + the speed movement stats (P#, judged from the
# ACTUAL cmd_lin of the speed-role frames) + metric means + blink events.
MASTER_COLUMNS = (
    ["session_id", "date", "subject", "subject_b", "device_mode", "metric", "electrode", "roles"]
    + TRIALS_CSV_COLUMNS[:5]        # run, trial_idx, a_state, b_state, b_direction
    + ["speed_intent", "steer_intent", "steer_direction", "clean_switch", "is_blink", "latency_ms"]
    + ["mean_cmd_lin", "moving_time_ratio", "speed_active"]
    + TRIALS_CSV_COLUMNS[-4:]       # mean_alpha, mean_tbr, mean_ei, blink_count
)

# P44②: the steering blink metrics are redefined as direction-switch
# correctness — rest natural blinks are NOT false triggers. dir_hit_rate =
# among steering trials where the target direction CHANGED, the fraction whose
# actual output direction matched the new target; dir_fa_rate = among steering
# trials where the target direction was steady, the fraction whose output
# direction changed anyway. Rest trials are excluded from both.
# P46: clean_switch_rate = among the 'needs switch' trials (target changed),
# the fraction whose output flipped EXACTLY the necessary number of times
# (toggles == needed, i.e. no overshoot / jitter / blink-carried-away) ≈
# 1 − false-trigger rate while switching; avg_toggles_per_switch = the mean
# flip count across those trials. Trials with no direction output are not
# judged (data gap, not a failure) and are excluded from both.
SUMMARY_COLUMNS = [
    "session_id", "run", "channel", "n_attention", "n_rest",
    "hit_rate", "fa_rate", "d_prime", "auc",
    "mean_score_attention", "mean_score_rest",
    "mean_latency_attention", "mean_latency_rest",
    "dir_hit_rate", "dir_fa_rate",
    "clean_switch_rate", "avg_toggles_per_switch",
]


# ── helpers ───────────────────────────────────────────────────────────────

def _f(v: Any) -> Optional[float]:
    """Numeric value → float, or None when missing / non-numeric (tolerant)."""
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _mean(vals: Iterable[Optional[float]]) -> Any:
    """Mean of the numeric values, or ``''`` when empty (fall back, not crash)."""
    f = [v for v in vals if v is not None]
    return round(sum(f) / len(f), 6) if f else ""


def _mode(vals: Iterable[str]) -> str:
    c = Counter(vals)
    return c.most_common(1)[0][0] if c else ""


def _dir_code(value: Any) -> Optional[str]:
    """Normalize a direction to 'right' / 'left' (or None). Accepts BOTH the
    protocol string ('left' / 'right') AND the node's numeric steer_direction
    (the documented convention 1 = right, -1 = left) — the P45 type mismatch
    that made dir_hit compare a number to a string and always fail."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("right", "1", "1.0"):
        return "right"
    if s in ("left", "-1", "-1.0"):
        return "left"
    return None


def direction_sequence(frames: list[dict]) -> list[str]:
    """P46: the trial's OUTPUT direction trajectory — the ordered non-empty
    steer_direction per frame, normalized to 'left'/'right' via ``_dir_code``
    (empty / missing frames carry no directional information and are dropped,
    so they never create a spurious toggle)."""
    seq = []
    for r in frames:
        d = _dir_code(r.get("steer_direction"))
        if d is not None:
            seq.append(d)
    return seq


def _switch_annotation(b_state: Any, b_direction: Any, prev_target: Optional[str],
                       toggles: Optional[int], start: Optional[str]) -> dict:
    """P46: per-trial clean-switch annotation.
    - ``target``: the normalized target direction (None for rest / unreadable).
    - ``needs_switch``: an ATTENTION trial whose target changed vs the previous
      attention trial — the 'needs a direction switch' set (rest trials don't
      set a direction requirement, so they don't break the sequence).
    - ``needed``: 0 when the trial's STARTING output already equals the target
      (no flip required), 1 otherwise — the direction is binary, so exactly
      one flip lands on target.
    - ``clean``: toggles == needed — the output flipped exactly the necessary
      number of times (parity makes 'ends on target' redundant: a 3-flip
      trajectory that ends on target still overshot twice). Computed for every
      attention trial with a target + direction output, so the master table
      can deep-dive steady-target trials too; the summary aggregates only the
      needs-switch subset.
    Computable values are None when the trial has no direction output / target
    (rest trial) — clean is then not judgeable."""
    target = _dir_code(b_direction) if b_state == "attention" else None
    needs_switch = bool(target and prev_target and target != prev_target)
    needed = clean = None
    if toggles is not None and target is not None:
        needed = 0 if start == target else 1
        clean = (toggles == needed)
    return {"target": target, "needs_switch": needs_switch,
            "needed": needed, "clean": clean}


def _speed_movement(frames: list[dict]) -> Optional[tuple]:
    """P#: the trial's ACTUAL forward movement, judged from the speed-role
    frames only — dual-device logs mix speed + steering frames in one trial
    file, and only the speed node's cmd_lin drives the car forward. Returns
    ``(mean_cmd_lin, moving_time_ratio, speed_active)`` or None when the trial
    has no speed-role frame with a readable cmd_lin (a steering-only session,
    or a data gap) — the caller then falls back to ``''`` / excludes the trial
    from the speed hit/FA, never a crash. ``speed_active`` = 1 when
    moving_time_ratio >= MOVING_RATIO_THRESHOLD (the trial count as
    successful)."""
    cms = [_f(r.get("cmd_lin")) for r in frames
           if str(r.get("role", "")).strip() == "speed" and _f(r.get("cmd_lin")) is not None]
    if not cms:
        return None
    moving = sum(1 for c in cms if c > SPEED_CMD_THRESHOLD)
    ratio = moving / len(cms)
    return (_mean(cms), round(ratio, 6), 1 if ratio >= MOVING_RATIO_THRESHOLD else 0)


def _read_csv(path: Path) -> list[dict]:
    """Tolerant CSV read — missing / empty / corrupt file yields []."""
    if not path.exists():
        return []
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except (OSError, csv.Error):
        return []


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def zscore(p: float) -> float:
    """Inverse normal CDF (probit) — Acklam's rational approximation, stdlib
    only (math.sqrt/log; ~1e-9 accuracy). p is clamped to (0,1) so a perfect
    hit / zero-FA rate still yields a finite d-prime (the clamp is an analysis
    assumption: cap the extreme z at ~±4.75)."""
    p = float(p)
    p = min(max(p, 1e-6), 1 - 1e-6)
    return _inv_normal_cdf(p)


def _inv_normal_cdf(p: float) -> float:
    """Acklam's inverse normal CDF (p must be strictly inside (0,1))."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p_low, p_high = 0.02425, 1.0 - 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        num = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
        den = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        return num / den
    if p <= p_high:
        q = p - 0.5
        r = q * q
        num = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        den = (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        return num / den
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    num = -((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]))
    den = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    return num / den


def auc_rank(attention: list[float], rest: list[float]) -> Any:
    """Rank-based AUC (the Mann-Whitney U statistic) — P(a random attention
    score exceeds a random rest score). Pure stdlib; ties get the average
    rank. Returns ``''`` when either side is empty."""
    n1, n2 = len(attention), len(rest)
    if n1 == 0 or n2 == 0:
        return ""
    items = [(float(s), 1) for s in attention] + [(float(s), 0) for s in rest]
    items.sort(key=lambda x: x[0])
    r1 = 0.0  # rank sum of the attention scores
    i = 0
    while i < len(items):
        j = i
        while j + 1 < len(items) and items[j + 1][0] == items[i][0]:
            j += 1
        avg = (i + j) / 2 + 1          # average rank across the tie block
        for k in range(i, j + 1):
            if items[k][1]:
                r1 += avg
        i = j + 1
    u1 = r1 - n1 * (n1 + 1) / 2
    return round(u1 / (n1 * n2), 6)


# ── data locations ────────────────────────────────────────────────────────

def default_data_dir() -> Path:
    """Mirror experiment._DEFAULT_DATA_DIR (EXPERIMENT_DATA_DIR wins)."""
    return Path(
        os.environ.get("EXPERIMENT_DATA_DIR") or (Path(__file__).resolve().parents[3] / "experiment_data")
    )


def default_out_dir(data_dir: Path | str) -> Path:
    return Path(data_dir) / "analysis"


# ── session loading ───────────────────────────────────────────────────────

def iter_sessions(data_dir: Path | str) -> Iterable[dict]:
    """Yield a dict per session subdir that has a readable session.json
    ({'dir', 'meta', 'trials'}); corrupt / missing-session.json dirs are
    skipped, never raised."""
    root = Path(data_dir)
    if not root.is_dir():
        return
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        sess = load_session(child)
        if sess is not None:
            yield sess


def load_session(session_dir: Path) -> Optional[dict]:
    """session.json + trials.csv (+ labels.csv tolerated). Missing or corrupt
    session.json → None (skip)."""
    sj = session_dir / "session.json"
    if not sj.exists():
        return None
    try:
        meta = json.loads(sj.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    trials = _read_csv(session_dir / "trials.csv")
    return {"dir": session_dir, "meta": meta, "trials": trials}


def read_trial_frames(session_dir: Path, trial_idx: int, run: Any = "") -> list[dict]:
    """The frame rows of the trial's CSV — ``run_<R>_trial_<NNN>.csv`` for a
    P44① run, or the legacy ``trial_<NNN>.csv`` when no run is tagged; missing
    → [] (the trial's output aggregates then fall back to '')."""
    if run:
        path = session_dir / f"run_{int(run):02d}_trial_{trial_idx:03d}.csv"
    else:
        path = session_dir / f"trial_{trial_idx:03d}.csv"
    return _read_csv(path)


def session_runs(trials_rows: list[dict]) -> dict:
    """Group trials.csv rows by run ('' = a legacy pre-P44 session). A session
    whose protocol was run multiple times (Start → Reset → Start) has several
    runs and they must NEVER be mixed."""
    runs: dict = {}
    for row in trials_rows:
        runs.setdefault(str(row.get("run", "")), []).append(row)
    return runs


def aggregate_frames(frames: list[dict]) -> dict:
    """Per-trial outputs from the frame rows — tolerant of empty values:
    missing frames → '' aggregates, never a crash."""
    speed = [_f(r.get("speed_intent")) for r in frames]
    steer = [_f(r.get("steer_intent")) for r in frames]
    lat = [_f(r.get("latency_ms")) for r in frames]
    dirs = [str(r.get("steer_direction", "")).strip() for r in frames
            if str(r.get("steer_direction", "")).strip()]
    blink = any(str(r.get("is_blink", "")).strip() not in ("", "0", "False", "false") for r in frames)
    # P46: the direction trajectory — 'toggles' = frame-by-frame flips of the
    # OUTPUT direction (None when the trial has no direction output);
    # 'start_direction' = the first output direction (None likewise).
    seq = direction_sequence(frames)
    toggles = None if not seq else sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    return {
        "speed_intent": _mean(speed),
        "steer_intent": _mean(steer),
        "steer_direction": _mode(dirs),
        # P45: the trial's FINAL output direction (a blink toggles the node's
        # steer_direction; the end state best reflects whether the switch
        # actually happened by the end of the trial).
        "steer_direction_last": dirs[-1] if dirs else "",
        "toggles": toggles,
        "start_direction": seq[0] if seq else None,
        "is_blink": 1 if blink else 0,
        "latency_ms": _mean(lat),
    }


# ── master long table ─────────────────────────────────────────────────────

def session_master_rows(session: dict) -> list[dict]:
    meta = session["meta"]
    m = meta.get("meta", {})
    sys = meta.get("system", {})
    roles = sys.get("roles") or []
    rows = []
    # P44①: iterate per RUN — a session re-run several times must never mix.
    for run, run_rows in session_runs(session["trials"]).items():
        # P46: track the previous attention trial's target so each trial knows
        # whether it 'needs a switch' (target changed).
        prev_target = None
        for t in run_rows:
            try:
                idx = int(t.get("trial_idx", 0))
            except (ValueError, TypeError):
                idx = 0
            frames = read_trial_frames(session["dir"], idx, run)
            agg = aggregate_frames(frames)
            mov = _speed_movement(frames)          # P#: ACTUAL forward movement
            ann = _switch_annotation(t.get("b_state"), t.get("b_direction"), prev_target,
                                     agg["toggles"], agg["start_direction"])
            if ann["target"] is not None:
                prev_target = ann["target"]
            clean = ann["clean"]
            rows.append({
                "session_id": meta.get("session_id", ""),
                "run": run,
                "date": m.get("date", ""),
                "subject": m.get("subject", ""),
                "subject_b": m.get("subject_b", ""),
                "device_mode": sys.get("device_mode", ""),
                "metric": sys.get("metric", ""),
                "electrode": m.get("electrode", ""),
                "roles": "/".join(roles),
                "trial_idx": idx,
                "a_state": t.get("a_state", ""),
                "b_state": t.get("b_state", ""),
                "b_direction": t.get("b_direction", ""),
                "speed_intent": agg["speed_intent"],
                "steer_intent": agg["steer_intent"],
                "steer_direction": agg["steer_direction"],
                # P46: 1 = the output flipped exactly the necessary number of
                # times; 0 = it overshot / jittered / was carried away; '' =
                # not judgeable (rest trial, no target, or no direction output).
                "clean_switch": "1" if clean is True else "0" if clean is False else "",
                "is_blink": agg["is_blink"],
                # P#: speed movement stats judged from the ACTUAL cmd_lin of
                # the speed-role frames ('' when the trial has no such frames —
                # a steering-only session / data gap).
                "mean_cmd_lin": mov[0] if mov else "",
                "moving_time_ratio": mov[1] if mov else "",
                "speed_active": mov[2] if mov else "",
                "mean_alpha": _f(t.get("mean_alpha")) if _f(t.get("mean_alpha")) is not None else "",
                "mean_tbr": _f(t.get("mean_tbr")) if _f(t.get("mean_tbr")) is not None else "",
                "mean_ei": _f(t.get("mean_ei")) if _f(t.get("mean_ei")) is not None else "",
                "latency_ms": agg["latency_ms"],
                "blink_count": _f(t.get("blink_count")) if _f(t.get("blink_count")) is not None else "",
            })
    return rows


# ── condition summary ─────────────────────────────────────────────────────

def session_summary_rows(session: dict) -> list[dict]:
    """One row per (session, run, channel): the channel's attention-vs-rest
    discrimination (hit rate / FA rate / d' / rank AUC), mean score + latency
    per state, and — for the steering channel only — the direction-switch
    correctness metrics (P44②) + the clean-switch quality metrics (P46)."""
    sys = session["meta"].get("system", {})
    roles = sys.get("roles") or []
    sid = session["meta"].get("session_id", "")
    rows = []
    for run, run_rows in session_runs(session["trials"]).items():
        trials = []
        prev_target = None          # P46: previous attention trial's target
        for t in run_rows:
            try:
                idx = int(t.get("trial_idx", 0))
            except (ValueError, TypeError):
                idx = 0
            frames = read_trial_frames(session["dir"], idx, run)
            agg = aggregate_frames(frames)
            mov = _speed_movement(frames)          # P#: ACTUAL forward movement
            ann = _switch_annotation(t.get("b_state"), t.get("b_direction"), prev_target,
                                     agg["toggles"], agg["start_direction"])
            if ann["target"] is not None:
                prev_target = ann["target"]
            trials.append({
                "a_state": t.get("a_state", ""),
                "b_state": t.get("b_state", ""),
                "b_direction": t.get("b_direction", ""),
                "score_a": agg["speed_intent"],
                "score_b": agg["steer_intent"],
                "steer_direction": agg["steer_direction_last"],   # P45: final state
                "toggles": agg["toggles"],                        # P46
                "needs_switch": ann["needs_switch"],              # P46
                "clean": ann["clean"],                            # P46
                # P#: speed hit/FA + AUC are judged from the ACTUAL cmd_lin of
                # the speed-role frames (None when the trial has no such frames
                # — excluded from the speed stats, never a crash).
                "mean_cmd_lin": mov[0] if mov else None,
                "speed_active": mov[2] if mov else None,
                "latency_ms": agg["latency_ms"],
            })
        for role in roles:
            if role == "speed":
                rows.append(_channel_summary_row(sid, run, "speed", trials,
                                                 state_key="a_state", score_key="score_a",
                                                 threshold=None, blink=False))
            elif role == "steering":
                rows.append(_channel_summary_row(sid, run, "steering", trials,
                                                 state_key="b_state", score_key="score_b",
                                                 threshold=STEER_HIT_THRESHOLD, blink=True))
    return rows


def _direction_switch_metrics(trials: list[dict]) -> tuple:
    """P44②: steering direction-switch correctness. Only ATTENTION (blink /
    direction) trials count — dir_hit = the output direction matches the
    target when the target CHANGED; dir_fa = the output direction changed
    while the target was steady. Rest trials are EXCLUDED (a rest natural
    blink is NOT a false trigger — relax is free action). Actual direction =
    the trial's FINAL steer_direction (a blink toggles the node's direction;
    the end state shows whether the switch happened). NOTE: dir_fa needs
    steady-target ATTENTION trials — the pre-P45 generator strictly
    alternated directions, so legacy protocols leave dir_fa empty by design
    (the P45 8-cycle produces pairs and measures it).

    P46: clean_switch_rate / avg_toggles_per_switch — direction control
    QUALITY, not just the end state. dir_hit/dir_fa judge only the final frame,
    so a subject who flips 3 times and lands on target counts as a 'hit'.
    clean-switch instead counts, among the 'needs switch' trials (attention
    trials whose target changed from the previous attention trial, precomputed
    per trial), the fraction whose output flipped EXACTLY the necessary number
    of times (toggles == needed) — a 3-flip trajectory is NOT clean even when
    it ends on target (2 flips were spurious: natural blinks / noise treated
    as active switches). avg_toggles_per_switch = the mean flip count across
    the same trials (1.0 ideal). Needs-switch trials with no direction output
    are excluded (a data gap, not a failure)."""
    seq = [t for t in trials
           if t.get("b_state") == "attention"
           and _dir_code(t.get("steer_direction")) is not None
           and _dir_code(t.get("b_direction")) is not None]
    if len(seq) < 2:
        return "", "", "", ""
    switched = switched_ok = steady = steady_fa = 0
    for i in range(1, len(seq)):
        # P45: BOTH sides are normalized to 'left'/'right' — the protocol
        # string AND the node's numeric steer_direction (1 = right, -1 = left).
        prev_t = _dir_code(seq[i - 1].get("b_direction"))
        target = _dir_code(seq[i].get("b_direction"))
        prev_a = _dir_code(seq[i - 1].get("steer_direction"))
        actual = _dir_code(seq[i].get("steer_direction"))
        if target != prev_t:
            switched += 1
            if actual == target:
                switched_ok += 1
        elif actual and actual != prev_a:
            steady += 1
            steady_fa += 1
        else:
            steady += 1
    dh = round(switched_ok / switched, 6) if switched else ""
    df = round(steady_fa / steady, 6) if steady else ""
    # P46: clean-switch quality over the needs-switch trials.
    sw = [t for t in trials if t.get("needs_switch") and t.get("toggles") is not None]
    if not sw:
        return dh, df, "", ""
    n_clean = sum(1 for t in sw if t.get("clean"))
    csr = round(n_clean / len(sw), 6)
    avg = round(sum(int(t["toggles"]) for t in sw) / len(sw), 6)
    return dh, df, csr, avg


def _channel_summary_row(session_id: str, run: Any, channel: str, trials: list[dict],
                         state_key: str, score_key: str, threshold: float | None,
                         blink: bool) -> dict:
    """Discrimination stats for one (channel × run). Only trials with a
    readable score are counted (a trial with no frames has no output to judge).

    P#: the SPEED channel is judged from the ACTUAL forward command — a trial
    is a hit / false alarm when it was moving (speed_active = moving_time_ratio
    >= MOVING_RATIO_THRESHOLD over its speed-role frames' cmd_lin >
    SPEED_CMD_THRESHOLD), NOT from the speed_intent classifier. AUC + the mean
    scores use the continuous mean_cmd_lin (all primary speed metrics are
    based on the actual command). Trials with no speed-role frames are not
    judged (a data gap, not a failure). The steering path is unchanged."""
    if channel == "speed":
        att = [t for t in trials if t[state_key] == "attention" and t.get("speed_active") is not None]
        rst = [t for t in trials if t[state_key] == "rest" and t.get("speed_active") is not None]
        n1, n2 = len(att), len(rst)
        hit = sum(1 for t in att if t["speed_active"]) if n1 else 0
        fa = sum(1 for t in rst if t["speed_active"]) if n2 else 0
        att_score = [t["mean_cmd_lin"] for t in att]
        rst_score = [t["mean_cmd_lin"] for t in rst]
    else:
        att = [t for t in trials if t[state_key] == "attention" and _f(t[score_key]) is not None]
        rst = [t for t in trials if t[state_key] == "rest" and _f(t[score_key]) is not None]
        n1, n2 = len(att), len(rst)
        att_score = [_f(t[score_key]) for t in att]
        rst_score = [_f(t[score_key]) for t in rst]
        hit = sum(1 for s in att_score if s > threshold) if n1 else 0
        fa = sum(1 for s in rst_score if s > threshold) if n2 else 0
    hit_rate = round(hit / n1, 6) if n1 else ""
    fa_rate = round(fa / n2, 6) if n2 else ""
    auc = auc_rank(att_score, rst_score)
    d_prime = round(zscore(hit_rate) - zscore(fa_rate), 6) if n1 and n2 else ""

    def _ml(rows_: list[dict]) -> Any:
        return _mean(_f(r["latency_ms"]) for r in rows_)

    row = {
        "session_id": session_id,
        "run": run,
        "channel": channel,
        "n_attention": n1,
        "n_rest": n2,
        "hit_rate": hit_rate,
        "fa_rate": fa_rate,
        "d_prime": d_prime,
        "auc": auc,
        "mean_score_attention": _mean(att_score),
        "mean_score_rest": _mean(rst_score),
        "mean_latency_attention": _ml(att),
        "mean_latency_rest": _ml(rst),
        "dir_hit_rate": "",
        "dir_fa_rate": "",
        "clean_switch_rate": "",
        "avg_toggles_per_switch": "",
    }
    if blink:
        (row["dir_hit_rate"], row["dir_fa_rate"],
         row["clean_switch_rate"], row["avg_toggles_per_switch"]) = \
            _direction_switch_metrics(trials)
    return row


# ── orchestrator + CLI ────────────────────────────────────────────────────

def export_all(data_dir: Path | str, out_dir: Optional[Path | str] = None) -> dict:
    """Scan ``data_dir`` → write master_trials.csv + condition_summary.csv in
    ``out_dir`` (default ``<data_dir>/analysis``). Returns the row counts."""
    data_dir = Path(data_dir)
    out_dir = Path(out_dir) if out_dir else default_out_dir(data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions = list(iter_sessions(data_dir))
    master = [row for sess in sessions for row in session_master_rows(sess)]
    summary = [row for sess in sessions for row in session_summary_rows(sess)]

    _write_csv(out_dir / "master_trials.csv", MASTER_COLUMNS, master)
    _write_csv(out_dir / "condition_summary.csv", SUMMARY_COLUMNS, summary)
    return {
        "sessions": len(sessions),
        "master_rows": len(master),
        "summary_rows": len(summary),
        "out_dir": str(out_dir),
    }


def main(argv: Optional[list[str]] = None) -> dict:
    ap = argparse.ArgumentParser(
        prog="python -m app.experiment_export",
        description="E5: export experiment_data/<session>/ records into analysis tables.",
    )
    ap.add_argument("--out", help="output directory (default: <data_dir>/analysis)")
    ap.add_argument("--data-dir", help="experiment data dir (default: EXPERIMENT_DATA_DIR or ./experiment_data)")
    args = ap.parse_args(argv)
    data_dir = Path(args.data_dir) if args.data_dir else default_data_dir()
    result = export_all(data_dir, args.out)
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
