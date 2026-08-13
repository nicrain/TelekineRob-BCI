"""P16 experiment mode (E1 logging / E3 state machine / E4 labels).

Pure-stdlib logic in experiment.py — no rclpy/pylsl/pydantic needed.
Fake clock drives the lazy phase machine deterministically.
"""
import csv
import json

import pytest

from app.experiment import (
    DEFAULT_PROTOCOL,
    ExperimentSession,
    SessionMeta,
    TrialSpec,
    TRIAL_CSV_COLUMNS,
    balanced_shuffle,
    config_summary,
    load_protocol,
    session_meta_from_request,
    shuffle_trials,
)
from app.models import AppConfig, EegConfig, EegConfig2


class _Clock:
    def __init__(self, t: float = 0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, secs: float) -> None:
        self.t += secs


def _trials(count: int = 8) -> list[TrialSpec]:
    return [
        TrialSpec(
            a_state="attention" if i % 2 == 0 else "rest",
            b_state="rest",
            b_direction="left",
            duration_sec=4.0,
            rest_sec=2.0,
        )
        for i in range(count)
    ]


def _frame(i: float, steer: int = 1, role: str = "speed", **over) -> dict:
    frame = {
        "ts": 100.0 + i,
        "cmd_vel_ts": 100.0 + i + 0.01,
        "source": "dev",
        "role": role,
        "metrics": {"alpha": 1.0 + i, "theta": 0.5, "beta": 0.2},
        "features": {"theta_beta": 2.0 + i, "beta_alpha_theta": 0.1 + i * 0.01},
        "intents": {"speed_intent": 0.6 + i * 0.01, "steer_intent": 0.5},
        "command_linear_x": 0.1,
        "command_angular_z": 0.0,
        "steer_direction": steer,
    }
    frame.update(over)
    return frame


# --- protocol parsing -----------------------------------------------------

def test_load_protocol_parses_default():
    proto = load_protocol(DEFAULT_PROTOCOL)
    assert proto["shuffle"] == "balanced"
    assert proto["prompt_sec"] > 0
    assert len(proto["trials"]) > 0
    assert all(t.a_state in ("attention", "rest") for t in proto["trials"])


def test_load_protocol_rejects_empty_trials(tmp_path):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"trials": []}))
    with pytest.raises(ValueError):
        load_protocol(p)


def test_load_protocol_rejects_bad_shuffle(tmp_path):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"shuffle": "nope", "trials": [_frame_spec()]}))
    with pytest.raises(ValueError):
        load_protocol(p)


def _frame_spec():
    return {"a_state": "attention", "b_state": "rest", "b_direction": "left"}


def test_trial_spec_rejects_invalid_targets():
    with pytest.raises(ValueError):
        TrialSpec(a_state="nope")
    with pytest.raises(ValueError):
        TrialSpec(b_state="up")
    with pytest.raises(ValueError):
        TrialSpec(b_direction="up")
    with pytest.raises(ValueError):
        TrialSpec(duration_sec=0)


# --- shuffle (none / random / balanced) -----------------------------------

def test_shuffle_none_preserves_order():
    ts = _trials()
    assert [t.a_state for t in shuffle_trials(ts, "none")] == [t.a_state for t in ts]


def test_shuffle_random_is_deterministic_with_seed_and_keeps_counts():
    ts = _trials(20)
    a = shuffle_trials(ts, "random", seed=42)
    b = shuffle_trials(ts, "random", seed=42)
    assert [t.a_state for t in a] == [t.a_state for t in b]   # deterministic
    assert [t.a_state for t in a] != [t.a_state for t in ts]  # really shuffled
    assert [t.a_state for t in a] != [t.a_state for t in shuffle_trials(ts, "random", seed=1)]
    assert sum(1 for t in a if t.a_state == "attention") == 10  # counts kept


def test_balanced_shuffle_alternates_and_keeps_counts():
    ts = _trials(20)  # 10 attention / 10 rest
    out = balanced_shuffle(ts, seed=7)
    states = [t.a_state for t in out]
    assert states.count("attention") == 10
    assert states.count("rest") == 10
    run = 1
    for i in range(1, len(states)):
        run = run + 1 if states[i] == states[i - 1] else 1
        assert run <= 2, "balanced shuffle left a long run of one target"


# --- P20: metadata auto-config from the live AppConfig --------------------

def _cfg(eeg2=None) -> AppConfig:
    return AppConfig(
        eeg=EegConfig(role="speed", policy="tbr", lsl_source_id="gtec_bci_core4"),
        eeg2=eeg2,
    )


def test_config_summary_single_headband():
    """P20: metric/device_mode/roles/devices derived from the actual config —
    a single headband yields no hybrid, no electrode."""
    summary = config_summary(_cfg())
    assert summary == {
        "metric": "tbr",
        "device_mode": "single",
        "roles": ["speed"],
        "devices": [{"role": "speed", "device": "headband", "lsl_source_id": "gtec_bci_core4"}],
        "has_hybrid": False,
    }


def test_config_summary_dual_with_hybrid():
    """Dual mode with a HybridBlack → has_hybrid True + both roles."""
    eeg2 = EegConfig2(role="steering", policy="ei", lsl_source_id="gtec_hybrid_black")
    summary = config_summary(_cfg(eeg2=eeg2))
    assert summary["metric"] == "tbr"      # device-1 policy
    assert summary["device_mode"] == "dual"
    assert summary["roles"] == ["speed", "steering"]
    assert summary["has_hybrid"] is True
    assert any(d["device"] == "hybrid" for d in summary["devices"])


def test_session_meta_derives_metric_and_mode_from_summary():
    """P20: metric/device_mode are never client-supplied — they come from the
    config summary; electrode is recorded when a hybrid is present."""
    meta = session_meta_from_request(
        subject="s", role="pilot", session_no=3, electrode="wet", date="2026-08-13",
        summary={"metric": "ei", "device_mode": "dual", "has_hybrid": True},
    )
    assert meta.metric == "ei"
    assert meta.device_mode == "dual"
    assert meta.electrode == "wet"
    assert meta.subject == "s" and meta.session_no == 3


def test_session_meta_drops_electrode_without_hybrid():
    """Single headband → electrode is forced empty even if the client sent one."""
    meta = session_meta_from_request(
        subject="s", role="pilot", session_no=1, electrode="wet", date="",
        summary={"metric": "tbr", "device_mode": "single", "has_hybrid": False},
    )
    assert meta.electrode == ""


def test_session_json_records_system_config(tmp_path):
    """P20: session.json separates hand-filled meta from the ACTUAL system
    config (metric/mode/roles/devices) recorded at configure time."""
    clock = _Clock(0.0)
    sess = ExperimentSession(data_dir=tmp_path, clock=clock)
    summary = {
        "metric": "ei", "device_mode": "dual", "roles": ["speed", "steering"],
        "devices": [
            {"role": "speed", "device": "headband", "lsl_source_id": "gtec_bci_core4"},
            {"role": "steering", "device": "hybrid", "lsl_source_id": "gtec_hybrid_black"},
        ],
        "has_hybrid": True,
    }
    sess.configure(SessionMeta(subject="s", session_no=2, electrode="dry"), _trials(1), system_summary=summary)

    data = json.loads((tmp_path / sess._session_id / "session.json").read_text(encoding="utf-8"))
    assert data["system"] == summary                     # actual config recorded
    assert data["meta"]["subject"] == "s"
    assert data["meta"]["electrode"] == "dry"
    assert "metric" not in data["meta"]                  # no hand metric field
    assert "device_mode" not in data["meta"]             # no hand mode field
    assert data["protocol"]["n_trials"] == 1


# --- session state machine (E3) + recording (E1) + labels (E4) ------------

def test_session_runs_protocol_with_recording(tmp_path):
    clock = _Clock(0.0)
    sess = ExperimentSession(data_dir=tmp_path, clock=clock)
    trials = [
        TrialSpec(a_state="attention", b_state="rest", b_direction="left", duration_sec=4, rest_sec=2),
        TrialSpec(a_state="rest", b_state="rest", b_direction="right", duration_sec=4, rest_sec=2),
    ]
    sid = sess.configure(
        SessionMeta(subject="subj", session_no=1, metric="tbr", device_mode="single"),
        trials, shuffle="none", prompt_sec=1,
    )
    assert sid.startswith("subj_s1_tbr_single_")
    assert sess.start() is True

    # prompt for trial 0 (target shown, E4 label written at prompt entry)
    st = sess.state()
    assert st["phase"] == "prompt" and st["trial_idx"] == 0
    assert st["target"]["a_state"] == "attention"

    # enter trial 0
    clock.advance(1.5)
    assert sess.state()["phase"] == "trial"

    # record three analysis frames during the trial; the node's wall clock
    # (cmd_vel_ts) sits just before the session's receive clock → 10 ms
    # transport latency.
    clock.advance(0.5)
    sess.on_frame(_frame(0, cmd_vel_ts=clock.t - 0.01))
    clock.advance(0.5)
    sess.on_frame(_frame(1, cmd_vel_ts=clock.t - 0.01))
    clock.advance(0.5)
    sess.on_frame(_frame(2, cmd_vel_ts=clock.t - 0.01))
    assert len(sess._samples) == 3

    # trial 0 ends → rest
    clock.advance(2.5)  # now 5.5 = phase_until → rest
    assert sess.state()["phase"] == "rest"

    # rest ends → next trial prompt → its trial
    clock.advance(2.5)  # now 8.0 = rest end → prompt for trial 1
    st = sess.state()
    assert st["phase"] == "prompt" and st["trial_idx"] == 1
    clock.advance(1.0)
    assert sess.state()["phase"] == "trial"  # trial 1 recording

    # finish the protocol → done
    clock.advance(4.0)
    assert sess.state()["phase"] == "rest"
    clock.advance(2.0)
    assert sess.state()["phase"] == "done"
    assert sess.state()["n_trials"] == 2

    # ── E1: on-disk artifacts ─────────────────────────────
    sdir = tmp_path / sid
    assert (sdir / "session.json").exists()
    assert (sdir / "labels.csv").exists()
    assert (sdir / "trials.csv").exists()
    assert (sdir / "trial_000.csv").exists()

    # trial CSV: schema + truth + timing columns per §2
    rows = list(csv.DictReader((sdir / "trial_000.csv").open(encoding="utf-8")))
    assert rows[0].keys() == set(TRIAL_CSV_COLUMNS)
    assert len(rows) == 3
    for r in rows:
        assert r["a_state"] == "attention"
        assert r["b_state"] == "rest"
        assert r["b_direction"] == "left"
        assert r["trial_start_ts"] == "1.5"
        assert r["trial_end_ts"] == "5.5"
        assert r["role"] == "speed"
        assert float(r["latency_ms"]) == pytest.approx(10.0, abs=0.1)  # row_ts - cmd_vel_ts

    # summary: n_samples + means
    sums = list(csv.DictReader((sdir / "trials.csv").open(encoding="utf-8")))
    assert len(sums) == 2
    assert sums[0]["trial_idx"] == "0"
    assert sums[0]["n_samples"] == "3"
    assert float(sums[0]["mean_alpha"]) == pytest.approx(2.0)  # mean of 1.0,2.0,3.0

    # ── E4: labels.csv — one truth row per trial at prompt entry ──
    labels = list(csv.DictReader((sdir / "labels.csv").open(encoding="utf-8")))
    assert len(labels) == 2
    assert labels[0] == {"trial_idx": "0", "phase": "prompt", "wall_ts": "0.0",
                         "a_state": "attention", "b_state": "rest", "b_direction": "left"}
    assert labels[1]["trial_idx"] == "1"
    assert labels[1]["a_state"] == "rest"
    assert labels[1]["b_direction"] == "right"


def test_no_recording_outside_trial_phase(tmp_path):
    clock = _Clock(0.0)
    sess = ExperimentSession(data_dir=tmp_path, clock=clock)
    sess.configure(SessionMeta(), _trials(2), prompt_sec=1)
    assert sess.start() is True

    # prompt phase — frames are ignored
    sess.on_frame(_frame(0))
    assert sess._samples == []

    # rest phase — ignored (after trial 0 ends)
    clock.advance(1.5)  # enter trial 0
    assert sess.state()["phase"] == "trial"
    clock.advance(4.0)  # trial 0 ends → rest
    assert sess.state()["phase"] == "rest"
    sess.on_frame(_frame(1))
    assert sess._samples == []

    # walk the rest of the protocol to done (each state() advances one due
    # phase) — a frame in the done phase is ignored too
    clock.advance(2.0)
    assert sess.state()["phase"] == "prompt"  # trial 1 prompt
    clock.advance(1.0)
    assert sess.state()["phase"] == "trial"
    clock.advance(4.0)
    assert sess.state()["phase"] == "rest"
    clock.advance(2.0)
    assert sess.state()["phase"] == "done"
    sess.on_frame(_frame(2))
    assert sess._samples == []


def test_blink_toggle_recorded_as_event(tmp_path):
    clock = _Clock(0.0)
    sess = ExperimentSession(data_dir=tmp_path, clock=clock)
    sess.configure(SessionMeta(), [TrialSpec(duration_sec=10, rest_sec=1)], prompt_sec=0)
    sess.start()
    clock.advance(1.0)  # into the trial (prompt_sec 0)
    sess.state()

    sess.on_frame(_frame(0, steer=1))
    sess.on_frame(_frame(1, steer=1))
    sess.on_frame(_frame(2, steer=-1))  # blink toggle
    sess.on_frame(_frame(3, steer=-1))

    blinks = [s["is_blink"] for s in sess._samples]
    assert blinks == [0, 0, 1, 0]


def test_pause_freezes_and_resume_extends(tmp_path):
    clock = _Clock(0.0)
    sess = ExperimentSession(data_dir=tmp_path, clock=clock)
    sess.configure(SessionMeta(), [TrialSpec(duration_sec=10, rest_sec=1)], prompt_sec=5)
    sess.start()

    assert sess.state()["phase"] == "prompt"
    sess.pause()
    assert sess.state()["phase"] == "paused"
    clock.advance(100.0)  # paused — no deadline expiry, remaining frozen at pause
    assert sess.state()["phase"] == "paused"
    assert sess.state()["remaining_sec"] == 0.0

    sess.resume()
    st = sess.state()
    assert st["phase"] == "prompt"
    assert st["remaining_sec"] == pytest.approx(5.0, abs=0.01)  # frozen at pause time
    clock.advance(5.0)
    assert sess.state()["phase"] == "trial"
