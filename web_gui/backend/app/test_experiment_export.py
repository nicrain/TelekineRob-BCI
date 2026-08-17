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
    auc_rank,
    export_all,
    zscore,
)


def _frame(idx, a_state, b_state, b_direction, speed, steer, steer_dir,
           latency, blink=False):
    row = dict.fromkeys(TRIAL_CSV_COLUMNS, "")
    row.update({
        "trial_idx": idx, "a_state": a_state, "b_state": b_state,
        "b_direction": b_direction, "speed_intent": speed, "steer_intent": steer,
        "steer_direction": steer_dir, "is_blink": 1 if blink else 0,
        "latency_ms": latency,
    })
    return row


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
    """Speed channel: attention mean speed 0.8/0.9 (>0.5 threshold) → hit 2/2;
    rest 0.1/0.2 → FA 0/2 → hit_rate 1.0, fa_rate 0.0, rank AUC 1.0."""
    _write_session(tmp_path, "s1", roles=("speed",), trials=[
        {"trial_idx": "0", "a_state": "attention", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "attention", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "2", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "3", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: [_frame(0, "attention", "rest", "left", 0.8, 0.0, "", 10.0)],
        1: [_frame(1, "attention", "rest", "left", 0.9, 0.0, "", 12.0)],
        2: [_frame(2, "rest", "rest", "left", 0.1, 0.0, "", 20.0)],
        3: [_frame(3, "rest", "rest", "left", 0.2, 0.0, "", 22.0)],
    })
    export_all(tmp_path, tmp_path / "out")
    rows = _read(tmp_path / "out" / "condition_summary.csv")
    assert len(rows) == 1
    r = rows[0]
    assert r["session_id"] == "s1" and r["channel"] == "speed"
    assert r["n_attention"] == "2" and r["n_rest"] == "2"
    assert float(r["hit_rate"]) == pytest.approx(1.0)
    assert float(r["fa_rate"]) == pytest.approx(0.0)
    assert float(r["auc"]) == pytest.approx(1.0)
    assert float(r["d_prime"]) > 0
    assert float(r["mean_score_attention"]) == pytest.approx(0.85)
    assert float(r["mean_score_rest"]) == pytest.approx(0.15)
    assert float(r["mean_latency_attention"]) == pytest.approx(11.0)
    assert float(r["mean_latency_rest"]) == pytest.approx(21.0)
    assert r["blink_hit_rate"] == ""      # speed channel: no blink metrics


def test_export_condition_summary_steering_blink(tmp_path):
    """Steering channel: b_state=attention steer 0.7/0.8 → hit 2/2; rest 0.2/0.1
    → FA 0/2; blink fired in 1 of 2 attention trials and 0 of 2 rest → blink
    hit 0.5, blink FA 0.0."""
    _write_session(tmp_path, "s2", roles=("steering",), trials=[
        {"trial_idx": "0", "a_state": "rest", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "rest", "b_state": "attention", "b_direction": "right", "n_samples": "1"},
        {"trial_idx": "2", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "3", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: [_frame(0, "rest", "attention", "left", 0.0, 0.7, "left", 9.0, blink=True)],
        1: [_frame(1, "rest", "attention", "right", 0.0, 0.8, "right", 11.0)],
        2: [_frame(2, "rest", "rest", "left", 0.0, 0.2, "", 30.0)],
        3: [_frame(3, "rest", "rest", "left", 0.0, 0.1, "", 31.0)],
    })
    export_all(tmp_path, tmp_path / "out")
    rows = _read(tmp_path / "out" / "condition_summary.csv")
    assert len(rows) == 1
    r = rows[0]
    assert r["channel"] == "steering"
    assert float(r["hit_rate"]) == pytest.approx(1.0)
    assert float(r["fa_rate"]) == pytest.approx(0.0)
    assert float(r["auc"]) == pytest.approx(1.0)
    assert float(r["blink_hit_rate"]) == pytest.approx(0.5)
    assert float(r["blink_fa_rate"]) == pytest.approx(0.0)


def test_export_dual_two_channels(tmp_path):
    """Dual session with speed + steering roles → two summary rows."""
    _write_session(tmp_path, "s3", roles=("speed", "steering"), trials=[
        {"trial_idx": "0", "a_state": "attention", "b_state": "attention", "b_direction": "left", "n_samples": "1"},
        {"trial_idx": "1", "a_state": "rest", "b_state": "rest", "b_direction": "left", "n_samples": "1"},
    ], frames={
        0: [_frame(0, "attention", "attention", "left", 0.8, 0.7, "left", 10.0)],
        1: [_frame(1, "rest", "rest", "left", 0.1, 0.2, "", 20.0)],
    })
    export_all(tmp_path, tmp_path / "out")
    rows = _read(tmp_path / "out" / "condition_summary.csv")
    assert [r["channel"] for r in rows] == ["speed", "steering"]
    assert rows[0]["n_attention"] == "1" and rows[0]["n_rest"] == "1"
    assert rows[1]["channel"] == "steering"


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
