"""E5 export tests — synthetic session dirs → master_trials + condition_summary.

Pure stdlib: builds fake session.json / trials.csv / trial_<NNN>.csv under a
tmp dir, runs ``export_all``, and asserts the long-table rows/columns and the
summary hit-rate / d' / AUC numbers.
"""
import csv
import json
from pathlib import Path

import pytest

from app.experiment import TRIAL_CSV_COLUMNS, TRIALS_CSV_COLUMNS
from app.experiment_export import (
    MASTER_COLUMNS,
    _switch_annotation,
    auc_rank,
    direction_sequence,
    export_all,
    zscore,
)


def _frame(idx, a_state, b_state, b_direction, speed, steer, steer_dir,
           latency, blink=False, role="speed", cmd_lin=0.0):
    row = dict.fromkeys(TRIAL_CSV_COLUMNS, "")
    row.update({
        "trial_idx": idx, "a_state": a_state, "b_state": b_state,
        "b_direction": b_direction, "speed_intent": speed, "steer_intent": steer,
        "steer_direction": steer_dir, "is_blink": 1 if blink else 0,
        "latency_ms": latency, "role": role, "cmd_lin": cmd_lin,
    })
    return row


def _speed_trial(idx, a_state, cmd_vals, n_frames=None):
    """A list of speed-role frames for one trial — ``cmd_vals`` = the cmd_lin
    per frame (all of them when ``n_frames`` given, tiled)."""
    vals = cmd_vals if n_frames is None else [cmd_vals] * n_frames
    return [_frame(idx, a_state, "rest", "left", 0.5, 0.0, "", 10.0, role="speed", cmd_lin=v)
            for v in vals]


def _write_session(tmp, name, roles=("speed",), subject="S01", subject_b="",
                   trials=None, frames=None):
    """Build a synthetic session dir. ``trials``: list of dicts (a subset of
    TRIALS_CSV_COLUMNS keys); ``frames``: {trial_idx: [frame dicts...]}."""
    d = tmp / name
    d.mkdir(parents=True)
    meta = {
        "session_id": name,
        "meta": {"subject": subject, "subject_b": subject_b, "role": "pilot",
                 "session_no": 1, "electrode": "", "date": "2026-08-15"},
        "system": {"metric": "tbr",
                   "device_mode": "single" if len(roles) == 1 else "dual",
                   "roles": list(roles), "devices": [], "has_hybrid": False},
        "protocol": {"shuffle": "none", "n_trials": len(trials or [])},
    }
    (d / "session.json").write_text(json.dumps(meta), encoding="utf-8")
    if trials is not None:
        with (d / "trials.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=TRIALS_CSV_COLUMNS)
            w.writeheader()
            for t in trials:
                row = dict.fromkeys(TRIALS_CSV_COLUMNS, "")
                row.update(t)
                w.writerow(row)
    for idx, frs in (frames or {}).items():
        with (d / f"trial_{idx:03d}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=TRIAL_CSV_COLUMNS)
            w.writeheader()
            w.writerows(frs)
    return d


def _read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ── master long table ─────────────────────────────────────────────────────

def test_export_master_rows_and_columns(tmp_path):
    _write_session(tmp_path, "sess1", roles=("speed",), trials=[
        {"trial_idx": "0", "a_state": "attention", "b_state": "rest", "b_direction": "left",
         "mean_alpha": "0.5", "mean_tbr": "0.6", "mean_ei": "0.7", "blink_count": "1", "n_samples": "2"},
        {"trial_idx": "1", "a_state": "rest", "b_state": "rest", "b_direction": "left",
         "mean_alpha": "0.1", "mean_tbr": "0.2", "mean_ei": "0.3", "blink_count": "0", "n_samples": "2"},
    ], frames={
        0: [_frame(0, "attention", "rest", "left", 0.8, 0.1, "left", 12.0, blink=True),
            _frame(0, "attention", "rest", "left", 0.9, 0.2, "left", 14.0)],
        1: [_frame(1, "rest", "rest", "left", 0.1, 0.3, "", 15.0),
            _frame(1, "rest", "rest", "left", 0.2, 0.1, "", 17.0)],
    })
    result = export_all(tmp_path, tmp_path / "analysis")
    assert result == {"sessions": 1, "master_rows": 2, "summary_rows": 1,
                      "out_dir": str(tmp_path / "analysis")}

    rows = _read(tmp_path / "analysis" / "master_trials.csv")
    assert list(rows[0].keys()) == MASTER_COLUMNS
    r0, r1 = rows
    assert r0["session_id"] == "sess1" and r0["subject"] == "S01"
    assert r0["roles"] == "speed" and r0["device_mode"] == "single"
    assert r0["a_state"] == "attention" and r0["b_direction"] == "left"
    assert float(r0["speed_intent"]) == pytest.approx(0.85)   # mean of 0.8/0.9
    assert float(r0["steer_intent"]) == pytest.approx(0.15)
    assert r0["steer_direction"] == "left"                    # mode of the frames
    assert r0["is_blink"] == "1"                              # a frame blinked
    assert float(r0["latency_ms"]) == pytest.approx(13.0)
    assert float(r0["mean_alpha"]) == pytest.approx(0.5)
    assert float(r0["blink_count"]) == pytest.approx(1.0)
    assert r1["a_state"] == "rest" and r1["steer_direction"] == ""
    assert float(r1["speed_intent"]) == pytest.approx(0.15)


# ── condition summary ─────────────────────────────────────────────────────

def test_export_condition_summary_speed(tmp_path):
    """P#: speed hit/FA judged from the ACTUAL cmd_lin — attention trials whose
    speed-role frames are mostly MOVING (> SPEED_CMD_THRESHOLD) → hit; rest
    trials stationary → no FA. AUC from the continuous mean_cmd_lin."""
    _write_session(tmp_path, "s1", roles=("speed",), trials=[
        {"trial_idx": "0", "a_state": "attention", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "attention", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "2", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "3", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: _speed_trial(0, "attention", 0.15, n_frames=10),   # moving → hit
        1: _speed_trial(1, "attention", 0.15, n_frames=10),   # moving → hit
        2: _speed_trial(2, "rest", 0.0, n_frames=10),         # stationary → no FA
        3: _speed_trial(3, "rest", 0.0, n_frames=10),         # stationary → no FA
    })
    export_all(tmp_path, tmp_path / "out")
    rows = _read(tmp_path / "out" / "condition_summary.csv")
    assert len(rows) == 1
    r = rows[0]
    assert r["session_id"] == "s1" and r["channel"] == "speed"
    assert r["n_attention"] == "2" and r["n_rest"] == "2"
    assert float(r["hit_rate"]) == pytest.approx(1.0)
    assert float(r["fa_rate"]) == pytest.approx(0.0)
    assert float(r["auc"]) == pytest.approx(1.0)       # att 0.15 vs rest 0.0
    assert float(r["d_prime"]) > 0
    assert float(r["mean_score_attention"]) == pytest.approx(0.15)
    assert float(r["mean_score_rest"]) == pytest.approx(0.0)
    assert r["dir_hit_rate"] == ""      # speed channel: no direction metrics

    # master: the three speed columns per trial (speed_active = ratio >= 0.10).
    master = _read(tmp_path / "out" / "master_trials.csv")
    assert [r["speed_active"] for r in master] == ["1", "1", "0", "0"]
    assert float(master[0]["mean_cmd_lin"]) == pytest.approx(0.15)
    assert float(master[0]["moving_time_ratio"]) == pytest.approx(1.0)


def test_export_speed_single_frame_below_ratio_is_not_success(tmp_path):
    """P# ①: one moving frame (cmd_lin > 0.02) but ratio < 10% → NOT a
    successful trial → not a hit."""
    _write_session(tmp_path, "s1b", roles=("speed",), trials=[
        {"trial_idx": "0", "a_state": "attention", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: _speed_trial(0, "attention", [0.0] * 19 + [0.05]),   # 1/20 = 5% moving
    })
    export_all(tmp_path, tmp_path / "out")
    master = _read(tmp_path / "out" / "master_trials.csv")
    assert master[0]["speed_active"] == "0"
    assert float(master[0]["moving_time_ratio"]) == pytest.approx(0.05)
    r = _read(tmp_path / "out" / "condition_summary.csv")[0]
    assert r["n_attention"] == "1" and r["hit_rate"] == "0.0"   # judged, not a hit


def test_export_speed_exactly_ten_percent_ratio_is_success(tmp_path):
    """P# ②: exactly 10% of frames moving (2/20) → ratio == threshold → a
    successful trial (>=)."""
    _write_session(tmp_path, "s1c", roles=("speed",), trials=[
        {"trial_idx": "0", "a_state": "attention", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: _speed_trial(0, "attention", [0.05] * 2 + [0.0] * 18),   # 2/20 = 10%
    })
    export_all(tmp_path, tmp_path / "out")
    master = _read(tmp_path / "out" / "master_trials.csv")
    assert master[0]["speed_active"] == "1"
    assert float(master[0]["moving_time_ratio"]) == pytest.approx(0.1)
    r = _read(tmp_path / "out" / "condition_summary.csv")[0]
    assert r["hit_rate"] == "1.0"


def test_export_condition_summary_steering_direction(tmp_path):
    """P44②: steering channel direction-switch metrics — b_state=attention
    steer 0.7/0.8 → hit 2/2, rest 0.2/0.1 → FA 0/2. dir_hit = the output
    direction matches the target when it CHANGED (trial 3: left→right,
    output right → 1/1); dir_fa = the output changed while the target was
    steady (trial 2 changed output under a steady left target → 1/2). Rest
    trials are excluded from the direction metrics."""
    _write_session(tmp_path, "s2", roles=("steering",), trials=[
        {"trial_idx": "0", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "2", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "3", "a_state": "rest", "b_state": "attention", "b_direction": "right", "n_samples": "1"},
        {"trial_idx": "4", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "5", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: [_frame(0, "rest", "attention", "left", 0.0, 0.7, "left", 9.0)],
        1: [_frame(1, "rest", "attention", "left", 0.0, 0.7, "left", 10.0)],
        2: [_frame(2, "rest", "attention", "left", 0.0, 0.8, "right", 11.0)],   # false switch (target steady left)
        3: [_frame(3, "rest", "attention", "right", 0.0, 0.8, "right", 12.0)],  # target changed, matched
        4: [_frame(4, "rest", "rest", "left", 0.0, 0.2, "", 30.0)],
        5: [_frame(5, "rest", "rest", "left", 0.0, 0.1, "", 31.0)],
    })
    export_all(tmp_path, tmp_path / "out")
    rows = _read(tmp_path / "out" / "condition_summary.csv")
    assert len(rows) == 1
    r = rows[0]
    assert r["channel"] == "steering"
    assert float(r["hit_rate"]) == pytest.approx(1.0)
    assert float(r["fa_rate"]) == pytest.approx(0.0)
    assert float(r["auc"]) == pytest.approx(1.0)
    # attention trials 0(left),1(left),2(left),3(right): target left→right
    # once (trial 3, matched) → dir_hit 1/1; steady left at trials 1,2 → the
    # output changed at trial 2 (right) → dir_fa 1/2.
    assert float(r["dir_hit_rate"]) == pytest.approx(1.0)
    assert float(r["dir_fa_rate"]) == pytest.approx(0.5)


def test_export_steering_dir_metric_normalizes_numeric_steer(tmp_path):
    """P45①: the node's NUMERIC steer_direction (1 = right, -1 = left) is
    normalized against the protocol's 'left'/'right' targets — the old code
    compared a number to a string and dir_hit was constant 0.0."""
    _write_session(tmp_path, "s4", roles=("steering",), trials=[
        {"trial_idx": "0", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "2", "a_state": "rest", "b_state": "attention", "b_direction": "right", "n_samples": "1"},
    ], frames={
        0: [_frame(0, "rest", "attention", "left", 0.0, 0.7, "-1", 9.0)],   # -1 = left
        1: [_frame(1, "rest", "attention", "left", 0.0, 0.7, "-1", 10.0)],  # steady left, output stayed
        2: [_frame(2, "rest", "attention", "right", 0.0, 0.8, "1", 11.0)],  # 1 = right, target changed
    })
    export_all(tmp_path, tmp_path / "out")
    rows = _read(tmp_path / "out" / "condition_summary.csv")
    r = rows[0]
    assert r["channel"] == "steering"
    assert float(r["dir_hit_rate"]) == pytest.approx(1.0)   # switched left→right, output matched
    assert float(r["dir_fa_rate"]) == pytest.approx(0.0)    # steady left, output stayed


def test_export_steering_dir_metric_empty_without_attention(tmp_path):
    """P45③: a session with no attention direction trials → dir_hit/dir_fa
    are empty strings, never a crash. P46: clean-switch metrics are empty too."""
    _write_session(tmp_path, "s5", roles=("steering",), trials=[
        {"trial_idx": "0", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: [_frame(0, "rest", "rest", "left", 0.0, 0.2, "", 30.0)],
    })
    export_all(tmp_path, tmp_path / "out")
    r = _read(tmp_path / "out" / "condition_summary.csv")[0]
    assert r["dir_hit_rate"] == "" and r["dir_fa_rate"] == ""
    assert r["clean_switch_rate"] == "" and r["avg_toggles_per_switch"] == ""
    # P46: the rest trial carries no clean_switch in the master table either.
    m = _read(tmp_path / "out" / "master_trials.csv")[0]
    assert m["clean_switch"] == ""


def test_export_clean_switch_trajectories(tmp_path):
    """P46: direction-control QUALITY — the per-trial clean flag and the
    clean_switch_rate / avg_toggles_per_switch aggregates over the 'needs
    switch' trials (attention trials whose target changed). The 5 synthetic
    trajectories: already aligned / single hit are CLEAN; 2 overshoots,
    3 jitters-to-target and a natural blink carried away are NOT — even the
    3-jitter trial ends ON target, which dir_hit would have scored as a hit."""
    _write_session(tmp_path, "s6", roles=("steering",), trials=[
        {"trial_idx": "0", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "rest", "b_state": "attention", "b_direction": "right", "n_samples": "1"},
        {"trial_idx": "2", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "3", "a_state": "rest", "b_state": "attention", "b_direction": "right", "n_samples": "1"},
        {"trial_idx": "4", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "5", "a_state": "rest", "b_state": "attention", "b_direction": "right", "n_samples": "1"},
        {"trial_idx": "6", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        # trial 0: baseline, output already on the left target.
        0: [_frame(0, "rest", "attention", "left", 0.0, 0.7, "left", 9.0)],
        # trial 1: target changed left→right BUT the output is already right
        # (起点已对) → toggles 0 == needed 0 → clean.
        1: [_frame(1, "rest", "attention", "right", 0.0, 0.7, "right", 10.0)],
        # trial 2: single hit — one flip right→left lands on the new target.
        2: [_frame(2, "rest", "attention", "left", 0.0, 0.7, "right", 10.0),
            _frame(2, "rest", "attention", "left", 0.0, 0.7, "left", 10.5)],
        # trial 3: two overshoots — right→left→right, ends OFF target.
        3: [_frame(3, "rest", "attention", "right", 0.0, 0.7, "left", 10.0),
            _frame(3, "rest", "attention", "right", 0.0, 0.7, "right", 10.5),
            _frame(3, "rest", "attention", "right", 0.0, 0.7, "left", 11.0)],
        # trial 4: three jitters that still END on the left target — dir_hit
        # would call this a hit, clean-switch correctly flags 2 spurious flips.
        4: [_frame(4, "rest", "attention", "left", 0.0, 0.7, "right", 10.0),
            _frame(4, "rest", "attention", "left", 0.0, 0.7, "left", 10.5),
            _frame(4, "rest", "attention", "left", 0.0, 0.7, "right", 11.0),
            _frame(4, "rest", "attention", "left", 0.0, 0.7, "left", 11.5)],
        # trial 5: natural blink carried the direction away — right→left→right,
        # ends OFF the right target.
        5: [_frame(5, "rest", "attention", "right", 0.0, 0.7, "left", 10.0),
            _frame(5, "rest", "attention", "right", 0.0, 0.7, "right", 10.5),
            _frame(5, "rest", "attention", "right", 0.0, 0.7, "left", 11.0)],
        # trial 6: rest trial — no direction output, excluded from everything.
        6: [_frame(6, "rest", "rest", "left", 0.0, 0.2, "", 30.0)],
    })
    export_all(tmp_path, tmp_path / "out")

    master = _read(tmp_path / "out" / "master_trials.csv")
    assert [r["clean_switch"] for r in master] == ["1", "1", "1", "0", "0", "0", ""]
    assert [r["b_state"] for r in master] == ["attention"] * 6 + ["rest"]

    rows = _read(tmp_path / "out" / "condition_summary.csv")
    assert len(rows) == 1
    r = rows[0]
    # all 6 attention trials are judged (mean steer 0.7 > 0.5 threshold).
    assert r["n_attention"] == "6" and float(r["hit_rate"]) == pytest.approx(1.0)
    # needs-switch trials = 1..5 (target alternates every trial). Clean =
    # trials 1,2 (toggles 0/1 == needed 0/1) → 2/5.
    assert float(r["clean_switch_rate"]) == pytest.approx(0.4)
    assert float(r["avg_toggles_per_switch"]) == pytest.approx(1.6)   # (0+1+2+3+2)/5
    # dir_hit cross-check: only 3/5 switched trials END on target (t1,t2,t4).
    assert float(r["dir_hit_rate"]) == pytest.approx(0.6)


def test_export_clean_switch_empty_without_target_change(tmp_path):
    """P46: attention trials with a STEADY target → no 'needs switch' trial →
    clean_switch_rate / avg_toggles_per_switch are empty strings, never a
    crash (master clean_switch still recorded per attention trial)."""
    _write_session(tmp_path, "s7", roles=("steering",), trials=[
        {"trial_idx": "0", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: [_frame(0, "rest", "attention", "left", 0.0, 0.7, "left", 9.0)],
        # jitter on a steady target: left→right→left, ends on target but
        # flipped twice → per-trial clean False.
        1: [_frame(1, "rest", "attention", "left", 0.0, 0.7, "left", 10.0),
            _frame(1, "rest", "attention", "left", 0.0, 0.7, "right", 10.5),
            _frame(1, "rest", "attention", "left", 0.0, 0.7, "left", 11.0)],
    })
    export_all(tmp_path, tmp_path / "out")
    r = _read(tmp_path / "out" / "condition_summary.csv")[0]
    assert r["clean_switch_rate"] == "" and r["avg_toggles_per_switch"] == ""
    # master still annotates the per-trial clean for the attention trials:
    # trial 0 stayed put (clean), trial 1 jittered twice (not clean).
    m = _read(tmp_path / "out" / "master_trials.csv")
    assert [row["clean_switch"] for row in m] == ["1", "0"]


def test_export_clean_switch_normalizes_numeric_steer(tmp_path):
    """P46: toggles count frame-by-frame flips of the NODE's numeric
    steer_direction (1 = right, -1 = left) — the trajectory -1,1,-1 flips
    twice even though the target (left) never required a flip."""
    _write_session(tmp_path, "s8", roles=("steering",), trials=[
        {"trial_idx": "0", "a_state": "rest", "b_state": "attention", "b_direction": "right", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: [_frame(0, "rest", "attention", "right", 0.0, 0.7, "1", 9.0)],
        1: [_frame(1, "rest", "attention", "left", 0.0, 0.7, "-1", 10.0),
            _frame(1, "rest", "attention", "left", 0.0, 0.7, "1", 10.5),
            _frame(1, "rest", "attention", "left", 0.0, 0.7, "-1", 11.0)],
    })
    export_all(tmp_path, tmp_path / "out")
    r = _read(tmp_path / "out" / "condition_summary.csv")[0]
    # trial 1: target changed right→left (needs switch), start -1=left ALREADY
    # equals the target → needed 0, but toggles 2 → NOT clean.
    assert float(r["clean_switch_rate"]) == pytest.approx(0.0)
    assert float(r["avg_toggles_per_switch"]) == pytest.approx(2.0)
    m = _read(tmp_path / "out" / "master_trials.csv")
    assert [row["clean_switch"] for row in m] == ["1", "0"]


# ── P46 pure helpers ───────────────────────────────────────────────────────

def test_direction_sequence_and_switch_annotation():
    """P46: the pure helpers — empty/missing frames drop out of the trajectory
    (they never create a spurious toggle); the annotation computes needed/clean
    and the needs-switch membership from the previous attention target."""
    frames = [
        {"steer_direction": "left"},
        {"steer_direction": ""},          # empty frame: carries no direction
        {"steer_direction": "-1"},        # numeric left = left (P45 normalization)
        {"steer_direction": "1"},         # numeric right
    ]
    assert direction_sequence(frames) == ["left", "left", "right"]
    assert direction_sequence([]) == []

    # attention trial, target changed right→left, output already on target →
    # needed 0, no flips → clean; needs_switch True.
    ann = _switch_annotation("attention", "left", "right", toggles=0, start="left")
    assert ann == {"target": "left", "needs_switch": True, "needed": 0, "clean": True}
    # rest trial: no target → nothing judgeable, never needs_switch.
    ann = _switch_annotation("rest", "left", "right", toggles=0, start="left")
    assert ann == {"target": None, "needs_switch": False, "needed": None, "clean": None}
    # steady target: not a needs-switch trial, but clean is still computed
    # for the master deep-dive column.
    ann = _switch_annotation("attention", "left", "left", toggles=1, start="left")
    assert ann["needs_switch"] is False and ann["clean"] is False
    # no direction output → toggles None → clean not judgeable.
    ann = _switch_annotation("attention", "left", "right", toggles=None, start=None)
    assert ann["needed"] is None and ann["clean"] is None


def test_export_runs_analyzed_separately(tmp_path):
    """P44①: two runs in one session produce separate master rows (run column)
    and one summary row per run — runs are never mixed."""
    d = tmp_path / "sess"
    d.mkdir(parents=True)
    json.dump({"session_id": "sess",
               "meta": {"subject": "S01", "subject_b": "", "date": "2026-08-15"},
               "system": {"metric": "tbr", "device_mode": "single", "roles": ["speed"]}},
              open(d / "session.json", "w"))
    with open(d / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=TRIALS_CSV_COLUMNS)
        w.writeheader()
        for run in (1, 2):
            row = dict.fromkeys(TRIALS_CSV_COLUMNS, "")
            row.update({"run": run, "trial_idx": "0", "a_state": "attention",
                        "b_state": "rest", "b_direction": "left", "n_samples": "1"})
            w.writerow(row)
    for run in (1, 2):
        with open(d / f"run_{run:02d}_trial_000.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=TRIAL_CSV_COLUMNS)
            w.writeheader()
            row = dict.fromkeys(TRIAL_CSV_COLUMNS, "")
            row.update({"trial_idx": "0", "speed_intent": "0.8" if run == 1 else "0.2",
                        "role": "speed", "cmd_lin": "0.15" if run == 1 else "0.0"})
            w.writerow(row)
    export_all(tmp_path, tmp_path / "out")
    master = _read(tmp_path / "out" / "master_trials.csv")
    assert [r["run"] for r in master] == ["1", "2"]
    assert float(master[0]["speed_intent"]) == pytest.approx(0.8)
    assert float(master[1]["speed_intent"]) == pytest.approx(0.2)
    summary = _read(tmp_path / "out" / "condition_summary.csv")
    assert [r["run"] for r in summary] == ["1", "2"]
    # P#: speed mean score = the actual mean_cmd_lin (0.15 moving / 0.0 stop).
    assert float(summary[0]["mean_score_attention"]) == pytest.approx(0.15)
    assert float(summary[1]["mean_score_attention"]) == pytest.approx(0.0)


def test_export_dual_two_channels(tmp_path):
    """P#: dual session — the speed row is judged from the speed-role frames
    only (④); the steering row is unchanged (⑤)."""
    _write_session(tmp_path, "s3", roles=("speed", "steering"), trials=[
        {"trial_idx": "0", "a_state": "attention", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        # trial 0: speed frames MOVING (0.15) + steering frames (ignored for speed).
        0: [_frame(0, "attention", "attention", "left", 0.8, 0.7, "left", 10.0, role="speed", cmd_lin=0.15) for _ in range(5)]
           + [_frame(0, "attention", "attention", "left", 0.8, 0.7, "left", 10.0, role="steering", cmd_lin=0.0) for _ in range(5)],
        # trial 1: speed frames STATIONARY (0.0) — the steering frames are
        # moving (0.3) but must be IGNORED for the speed judgment.
        1: [_frame(1, "rest", "rest", "left", 0.1, 0.2, "", 20.0, role="speed", cmd_lin=0.0) for _ in range(5)]
           + [_frame(1, "rest", "rest", "left", 0.1, 0.2, "", 20.0, role="steering", cmd_lin=0.3) for _ in range(5)],
    })
    export_all(tmp_path, tmp_path / "out")
    rows = _read(tmp_path / "out" / "condition_summary.csv")
    assert [r["channel"] for r in rows] == ["speed", "steering"]
    speed, steer = rows
    # speed: trial 0 (attention) moving → hit 1/1; trial 1 (rest) stationary →
    # no FA (the steering frames' 0.3 cmd_lin are NOT counted).
    assert speed["n_attention"] == "1" and speed["n_rest"] == "1"
    assert float(speed["hit_rate"]) == pytest.approx(1.0)
    assert float(speed["fa_rate"]) == pytest.approx(0.0)
    assert float(speed["mean_score_attention"]) == pytest.approx(0.15)
    assert float(speed["mean_score_rest"]) == pytest.approx(0.0)
    # steering row: unchanged behavior (hit 1/1 from steer 0.7; a single
    # attention trial → direction metrics empty).
    assert steer["channel"] == "steering"
    assert float(steer["hit_rate"]) == pytest.approx(1.0)
    assert float(steer["fa_rate"]) == pytest.approx(0.0)
    assert steer["dir_hit_rate"] == "" and steer["dir_fa_rate"] == ""
    assert steer["clean_switch_rate"] == "" and steer["avg_toggles_per_switch"] == ""

    # master: trial 0 speed_active=1 (speed frames all moving), trial 1 = 0.
    master = _read(tmp_path / "out" / "master_trials.csv")
    assert [r["speed_active"] for r in master] == ["1", "0"]
    assert float(master[1]["mean_cmd_lin"]) == pytest.approx(0.0)   # steering ignored


# ── tolerance + determinism ───────────────────────────────────────────────

def test_export_missing_files_tolerated(tmp_path):
    """A session with trials.csv but NO trial_*.csv → master rows with '' output
    aggregates and a summary with no judged trials; junk / corrupt dirs are
    skipped without crashing."""
    _write_session(tmp_path, "no_frames", trials=[
        {"trial_idx": "0", "a_state": "attention", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={})
    (tmp_path / "junk").mkdir()                       # no session.json
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "session.json").write_text("{not json", encoding="utf-8")  # corrupt
    result = export_all(tmp_path, tmp_path / "out")
    assert result["sessions"] == 1
    assert result["master_rows"] == 1
    rows = _read(tmp_path / "out" / "master_trials.csv")
    assert rows[0]["speed_intent"] == "" and rows[0]["latency_ms"] == ""
    summary = _read(tmp_path / "out" / "condition_summary.csv")
    assert summary[0]["n_attention"] == "0" and summary[0]["n_rest"] == "0"
    assert summary[0]["hit_rate"] == ""


def test_export_deterministic(tmp_path):
    _write_session(tmp_path, "s1", roles=("speed",), trials=[
        {"trial_idx": "0", "a_state": "attention", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: [_frame(0, "attention", "rest", "left", 0.8, 0.0, "", 10.0)],
        1: [_frame(1, "rest", "rest", "left", 0.1, 0.0, "", 20.0)],
    })
    export_all(tmp_path, tmp_path / "a1")
    export_all(tmp_path, tmp_path / "a2")
    for fn in ("master_trials.csv", "condition_summary.csv"):
        assert (tmp_path / "a1" / fn).read_text(encoding="utf-8") == \
               (tmp_path / "a2" / fn).read_text(encoding="utf-8")


# ── E6: GET /api/experiment/export endpoint ───────────────────────────────

def test_export_endpoint_success(monkeypatch):
    """E6: the export endpoint returns {ok, output_dir, master_trials,
    condition_summary} on success."""
    import app.main as main
    monkeypatch.setattr(main, "default_data_dir", lambda: Path("/fake"))
    monkeypatch.setattr(main, "export_all", lambda data_dir, out_dir=None: {
        "sessions": 2, "master_rows": 10, "summary_rows": 3,
        "out_dir": "/fake/analysis"})
    result = main.exp_export()
    assert result == {"ok": True, "output_dir": "/fake/analysis",
                      "master_trials": 10, "condition_summary": 3}


def test_export_endpoint_failure(monkeypatch):
    """E6: a failed export returns {ok:false, message} — never a 500."""
    import app.main as main
    monkeypatch.setattr(main, "default_data_dir", lambda: Path("/fake"))

    def boom(data_dir, out_dir=None):
        raise RuntimeError("corrupt session")

    monkeypatch.setattr(main, "export_all", boom)
    result = main.exp_export()
    assert result["ok"] is False
    assert "corrupt session" in result["message"]


# ── pure stats helpers ────────────────────────────────────────────────────

def test_auc_rank_and_zscore():
    assert auc_rank([0.8, 0.9], [0.1, 0.2]) == 1.0
    assert auc_rank([0.1, 0.2], [0.8, 0.9]) == 0.0
    assert auc_rank([0.5, 0.5], [0.5, 0.5]) == 0.5      # all ties
    assert auc_rank([], [0.1]) == ""                     # empty side
    assert zscore(0.5) == pytest.approx(0.0)             # probit midpoint
    assert zscore(0.9772) == pytest.approx(2.0, abs=1e-3)
    assert zscore(0.0) < 0 and zscore(1.0) > 0           # clamped, finite
