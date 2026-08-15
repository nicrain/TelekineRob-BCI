"""E5: export experiment_data/<session>/ records into analysis tables.

Reads every session under the experiment data dir (respects
``EXPERIMENT_DATA_DIR``) and writes:

  master_trials.csv       — one row per trial, ALL sessions (long table)
  condition_summary.csv   — one row per (session, channel) discrimination stats

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
SPEED_HIT_THRESHOLD = 0.5   # mean speed_intent > this → attention hit
STEER_HIT_THRESHOLD = 0.5   # mean steer_intent > this → attention hit

# master_trials.csv columns: session fields + the target trio + the per-trial
# outputs (names aligned with the frame / trial-summary CSVs) + metric means +
# the blink event count.
MASTER_COLUMNS = (
    ["session_id", "date", "subject", "subject_b", "device_mode", "metric", "electrode", "roles"]
    + TRIALS_CSV_COLUMNS[:4]        # trial_idx, a_state, b_state, b_direction
    + ["speed_intent", "steer_intent", "steer_direction", "is_blink", "latency_ms"]
    + TRIALS_CSV_COLUMNS[-4:]       # mean_alpha, mean_tbr, mean_ei, blink_count
)

SUMMARY_COLUMNS = [
    "session_id", "channel", "n_attention", "n_rest",
    "hit_rate", "fa_rate", "d_prime", "auc",
    "mean_score_attention", "mean_score_rest",
    "mean_latency_attention", "mean_latency_rest",
    "blink_hit_rate", "blink_fa_rate",
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


def read_trial_frames(session_dir: Path, trial_idx: int) -> list[dict]:
    """The frame rows of ``trial_<NNN>.csv`` (TRIAL_CSV_COLUMNS); missing →
    [] (the trial's output aggregates then fall back to '')."""
    return _read_csv(session_dir / f"trial_{trial_idx:03d}.csv")


def aggregate_frames(frames: list[dict]) -> dict:
    """Per-trial outputs from the frame rows — tolerant of empty values:
    missing frames → '' aggregates, never a crash."""
    speed = [_f(r.get("speed_intent")) for r in frames]
    steer = [_f(r.get("steer_intent")) for r in frames]
    lat = [_f(r.get("latency_ms")) for r in frames]
    dirs = [str(r.get("steer_direction", "")).strip() for r in frames
            if str(r.get("steer_direction", "")).strip()]
    blink = any(str(r.get("is_blink", "")).strip() not in ("", "0", "False", "false") for r in frames)
    return {
        "speed_intent": _mean(speed),
        "steer_intent": _mean(steer),
        "steer_direction": _mode(dirs),
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
    for t in session["trials"]:
        try:
            idx = int(t.get("trial_idx", 0))
        except (ValueError, TypeError):
            idx = 0
        agg = aggregate_frames(read_trial_frames(session["dir"], idx))
        rows.append({
            "session_id": meta.get("session_id", ""),
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
            "is_blink": agg["is_blink"],
            "mean_alpha": _f(t.get("mean_alpha")) if _f(t.get("mean_alpha")) is not None else "",
            "mean_tbr": _f(t.get("mean_tbr")) if _f(t.get("mean_tbr")) is not None else "",
            "mean_ei": _f(t.get("mean_ei")) if _f(t.get("mean_ei")) is not None else "",
            "latency_ms": agg["latency_ms"],
            "blink_count": _f(t.get("blink_count")) if _f(t.get("blink_count")) is not None else "",
        })
    return rows


# ── condition summary ─────────────────────────────────────────────────────

def session_summary_rows(session: dict) -> list[dict]:
    """One row per (session, channel): the channel's attention-vs-rest
    discrimination (hit rate / FA rate / d' / rank AUC), mean score + latency
    per state, and — for the steering channel only — blink hit / FA rates."""
    sys = session["meta"].get("system", {})
    roles = sys.get("roles") or []
    sid = session["meta"].get("session_id", "")
    # per-trial aggregates, one pass over the frames
    trials = []
    for t in session["trials"]:
        try:
            idx = int(t.get("trial_idx", 0))
        except (ValueError, TypeError):
            idx = 0
        agg = aggregate_frames(read_trial_frames(session["dir"], idx))
        trials.append({
            "a_state": t.get("a_state", ""),
            "b_state": t.get("b_state", ""),
            "score_a": agg["speed_intent"],
            "score_b": agg["steer_intent"],
            "is_blink": agg["is_blink"],
            "latency_ms": agg["latency_ms"],
        })
    rows = []
    for role in roles:
        if role == "speed":
            rows.append(_channel_summary_row(sid, "speed", trials,
                                             state_key="a_state", score_key="score_a",
                                             threshold=SPEED_HIT_THRESHOLD, blink=False))
        elif role == "steering":
            rows.append(_channel_summary_row(sid, "steering", trials,
                                             state_key="b_state", score_key="score_b",
                                             threshold=STEER_HIT_THRESHOLD, blink=True))
    return rows


def _channel_summary_row(session_id: str, channel: str, trials: list[dict],
                         state_key: str, score_key: str, threshold: float,
                         blink: bool) -> dict:
    """Discrimination stats for one channel. Only trials with a readable
    score are counted (a trial with no frames has no output to judge)."""
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
        "blink_hit_rate": "",
        "blink_fa_rate": "",
    }
    if blink and n1 and n2:
        # 眨眼命中 = blink fired on an attention (blink-target) trial; 误触发
        # = blink fired on a rest trial — both per the channel's target state.
        row["blink_hit_rate"] = round(sum(1 for t in att if t["is_blink"]) / n1, 6)
        row["blink_fa_rate"] = round(sum(1 for t in rst if t["is_blink"]) / n2, 6)
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
