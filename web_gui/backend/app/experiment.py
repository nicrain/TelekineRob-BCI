"""Experiment mode (P16): per-trial ground-truth-labelled logging (E1/E4)
+ protocol-driven trial state machine + prompt/rest UI state (E3).

Schema contract: docs/EXPERIMENT_PLAN.md §2 — every session writes into
``<data_dir>/<session_id>/``:

    session.json          # metadata + shuffled protocol (reproducibility)
    labels.csv            # E4 label stream: one row per trial at prompt entry
                          # (wall-clock ts → aligned to the sample row_ts clock)
    trials.csv            # one summary row per trial (truth + start/end + means)
    trial_<NNN>.csv       # per-trial sample rows (truth columns repeated for
                          # self-containment; §2 #5 output + #6 timing)

Sample row timing columns: ``row_ts`` (backend receive, wall clock —
the alignment clock shared with labels.csv), ``frame_ts`` (the eeg node's
own frame timestamp), ``cmd_vel_ts`` (wall clock when the node published
the command). ``latency_ms`` = transport delay from node command publish
to backend receive (both wall clock). Precise eeg-node-internal pipeline
stages are a node-side concern (E2/follow-up); the label↔sample alignment
here is by ``row_ts``.

Pure stdlib (thread-safe recorder); importable and unit-testable with no
rclpy/pylsl/pydantic — the web GUI injects analysis frames via
``on_frame()``.
"""

from __future__ import annotations

import csv
import json
import os
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

PHASE_IDLE = "idle"
PHASE_PROMPT = "prompt"
PHASE_TRIAL = "trial"
PHASE_REST = "rest"
PHASE_PAUSED = "paused"
PHASE_DONE = "done"

PROMPT_SEC = 5.0  # P43: default Get-ready prompt (now the ONLY between-trial countdown)
REST_SEC = 10.0

# Repo-root experiment_data/ (gitignored); EXPERIMENT_DATA_DIR overrides.
_DEFAULT_DATA_DIR = Path(
    os.environ.get("EXPERIMENT_DATA_DIR") or (Path(__file__).resolve().parents[3] / "experiment_data")
)

TRIAL_CSV_COLUMNS = [
    "trial_idx", "a_state", "b_state", "b_direction",
    "trial_start_ts", "trial_end_ts",
    "row_ts", "frame_ts", "cmd_vel_ts", "source", "role",
    "alpha", "theta", "beta", "tbr", "ei",
    "speed_intent", "steer_intent", "steer_direction",
    "cmd_lin", "cmd_ang", "is_blink", "latency_ms",
]

LABELS_CSV_COLUMNS = ["trial_idx", "phase", "wall_ts", "a_state", "b_state", "b_direction"]

TRIALS_CSV_COLUMNS = [
    "trial_idx", "a_state", "b_state", "b_direction",
    "prompt_ts", "start_ts", "end_ts", "duration_sec",
    "n_samples", "mean_alpha", "mean_tbr", "mean_ei", "blink_count",
]

_STATE_OPTS = {"attention", "rest"}
_DIR_OPTS = {"left", "right"}
_METRIC_OPTS = {"alpha", "tbr", "ei"}
_MODE_OPTS = {"single", "dual"}
_PHASES = {PHASE_IDLE, PHASE_PROMPT, PHASE_TRIAL, PHASE_REST, PHASE_PAUSED, PHASE_DONE}

# P20: physical device inferred from the configured LSL source id (the same
# mapping the frontend uses). Used only to decide electrode applicability —
# the recorded "devices" block keeps the raw source ids too.
_SOURCE_TO_DEVICE = {"gtec_bci_core4": "headband", "gtec_hybrid_black": "hybrid"}


def device_entry(role: str, lsl_source_id: str, metric: str = "tbr") -> dict:
    """One configured device: role + physical device + per-device metric
    (P24/P25) + the raw source id. ``metric`` comes from the device's policy —
    the frontend path (ExperimentConfigSummary) and this backend fallback
    path now record it identically."""
    source = (lsl_source_id or "").strip()
    return {
        "role": role,
        "device": _SOURCE_TO_DEVICE.get(source, source),
        "metric": metric,
        "lsl_source_id": source,
    }


def config_summary(cfg) -> dict:
    """Actual experiment config, derived from the live AppConfig (P20).

    ``cfg`` is duck-typed (``.eeg`` / ``.eeg2`` / ``.launch``) so this stays
    stdlib-importable — the caller passes the pydantic AppConfig instance.
    This is the SOURCE OF TRUTH for the recorded metric/device_mode: the
    panel no longer hand-fills them, eliminating mis-labelled records.
    """
    eeg = cfg.eeg
    devices = [device_entry(eeg.role, eeg.lsl_source_id, eeg.policy)]
    eeg2 = getattr(cfg, "eeg2", None)
    if eeg2 is not None:
        devices.append(device_entry(eeg2.role, eeg2.lsl_source_id, eeg2.policy))
    return {
        "metric": eeg.policy,
        "device_mode": "dual" if eeg2 is not None else "single",
        "roles": [d["role"] for d in devices],
        "devices": devices,
        "has_hybrid": any(d["device"] == "hybrid" for d in devices),
    }


@dataclass
class TrialSpec:
    """One trial's target + duration (protocol)."""
    a_state: str = "attention"
    b_state: str = "rest"
    b_direction: str = "left"
    duration_sec: float = 20.0
    rest_sec: float = REST_SEC

    def __post_init__(self) -> None:
        if self.a_state not in _STATE_OPTS:
            raise ValueError(f"a_state must be in {sorted(_STATE_OPTS)}, got {self.a_state!r}")
        if self.b_state not in _STATE_OPTS:
            raise ValueError(f"b_state must be in {sorted(_STATE_OPTS)}, got {self.b_state!r}")
        if self.b_direction not in _DIR_OPTS:
            raise ValueError(f"b_direction must be in {sorted(_DIR_OPTS)}, got {self.b_direction!r}")
        if float(self.duration_sec) <= 0:
            raise ValueError(f"duration_sec must be > 0, got {self.duration_sec!r}")


@dataclass
class SessionMeta:
    """§2 #7 session metadata (recorded into session.json).

    P24: ``subject_b`` is device B's operator (dual mode); empty in single
    mode. The data-dir name carries both subjects in dual mode."""
    subject: str = ""
    subject_b: str = ""
    role: str = "pilot"
    session_no: int = 1
    metric: str = "tbr"
    device_mode: str = "single"
    electrode: str = ""
    date: str = ""

    def __post_init__(self) -> None:
        if self.metric not in _METRIC_OPTS:
            raise ValueError(f"metric must be in {sorted(_METRIC_OPTS)}, got {self.metric!r}")
        if self.device_mode not in _MODE_OPTS:
            raise ValueError(f"device_mode must be in {sorted(_MODE_OPTS)}, got {self.device_mode!r}")


def session_meta_from_request(
    subject: str,
    subject_b: str,
    role: str,
    session_no: int,
    electrode: str,
    date: str,
    summary: dict,
) -> SessionMeta:
    """Build the recorded SessionMeta from hand-filled fields + the ACTUAL
    config summary (P20): metric/device_mode always come from ``summary``
    (never the client); electrode is recorded only when a hybrid is present.
    P24: ``subject_b`` (device B, dual mode) is carried through.
    """
    return SessionMeta(
        subject=subject,
        subject_b=subject_b,
        role=role,
        session_no=int(session_no),
        metric=summary["metric"],
        device_mode=summary["device_mode"],
        electrode=electrode if summary.get("has_hybrid") else "",
        date=date,
    )


def _cond_key(trial: TrialSpec) -> tuple:
    return (trial.a_state, trial.b_state, trial.b_direction)


def balanced_shuffle(trials: list[TrialSpec], seed: Optional[int] = None) -> list[TrialSpec]:
    """Round-robin over condition buckets so no long runs of one target.

    Each condition bucket is shuffled first (random within condition), then
    dequeued one-at-a-time in stable bucket order — balanced target exposure
    AND no fatigue-inducing streaks (防顺序效应, plan §1.4/§1.5).
    """
    rnd = random.Random(seed)
    buckets: dict[tuple, list] = {}
    for t in trials:
        buckets.setdefault(_cond_key(t), []).append(t)
    for bucket in buckets.values():
        rnd.shuffle(bucket)
    out: list[TrialSpec] = []
    while any(buckets.values()):
        for key in list(buckets.keys()):
            if buckets[key]:
                out.append(buckets[key].pop(0))
        buckets = {k: v for k, v in buckets.items() if v}
    return out


def shuffle_trials(trials: list[TrialSpec], mode: str, seed: Optional[int] = None) -> list[TrialSpec]:
    """``none`` keeps file order; ``random`` shuffles; ``balanced`` round-robins."""
    if mode == "none":
        return list(trials)
    if mode == "random":
        rnd = random.Random(seed)
        out = list(trials)
        rnd.shuffle(out)
        return out
    if mode == "balanced":
        return balanced_shuffle(trials, seed=seed)
    raise ValueError(f"unknown shuffle mode {mode!r} (valid: none/random/balanced)")


def trial_dict(trial: TrialSpec) -> dict:
    return {
        "a_state": trial.a_state,
        "b_state": trial.b_state,
        "b_direction": trial.b_direction,
        "duration_sec": trial.duration_sec,
        "rest_sec": trial.rest_sec,
    }


def _mean(values: list[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


class ExperimentSession:
    """Thread-safe session recorder + protocol controller.

    The trial state machine is derived from wall time (lazy ``_advance`` on
    every ``state()`` / ``on_frame()`` call) — no background thread, no
    drift between the operator's view and the recorder. ``on_frame()`` is
    wired to the RosBridge analysis handler: samples are recorded only while
    the phase is ``trial`` (E1), and the ground-truth label is written at
    prompt entry (E4) on the same wall clock as the samples.
    """

    def __init__(
        self,
        data_dir: str | Path = _DEFAULT_DATA_DIR,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._clock = clock
        self._lock = threading.RLock()

        self._meta: Optional[SessionMeta] = None
        self._trials: list[TrialSpec] = []
        self._shuffle = "none"
        self._seed: Optional[int] = None
        self._prompt_sec = PROMPT_SEC

        self._session_id = ""
        self._session_dir: Optional[Path] = None
        self._labels_writer: Optional[csv.DictWriter] = None
        self._trials_writer: Optional[csv.DictWriter] = None
        self._labels_fh: Any = None
        self._trials_fh: Any = None
        self._system_summary: dict = {}

        self._phase = PHASE_IDLE
        self._trial_idx = 0
        self._phase_until = 0.0
        self._paused_from = PHASE_IDLE
        self._paused_remaining = 0.0
        self._trial_start = 0.0
        self._trial_end = 0.0
        self._prompt_ts = 0.0
        self._samples: list[dict] = []
        self._prev_steer: dict[str, int] = {}

    # ── configuration ────────────────────────────────────────────────────

    def configure(
        self,
        meta: SessionMeta,
        trials: list[TrialSpec],
        shuffle: str = "none",
        seed: Optional[int] = None,
        prompt_sec: Optional[float] = None,
        system_summary: Optional[dict] = None,
    ) -> str:
        """Start a new session: reset state, shuffle the protocol, write
        session.json. Returns the session id.

        ``system_summary`` (P20) is the ACTUAL runtime config (metric /
        device_mode / roles / devices) captured at configure time — recorded
        verbatim into session.json so the label truth matches the run.
        """
        ordered = shuffle_trials(trials, shuffle, seed=seed)
        with self._lock:
            self._close_files_locked()
            self._meta = meta
            self._trials = ordered
            self._shuffle = shuffle
            self._seed = seed
            self._prompt_sec = float(prompt_sec if prompt_sec is not None else PROMPT_SEC)
            self._system_summary = dict(system_summary or {})

            self._session_id = self._make_session_id(meta)
            self._session_dir = self._data_dir / self._session_id
            self._session_dir.mkdir(parents=True, exist_ok=True)
            self._write_session_json()
            self._open_files_locked()

            self._phase = PHASE_IDLE
            self._trial_idx = 0
            self._samples = []
            self._prev_steer = {}
            return self._session_id

    def _make_session_id(self, meta: SessionMeta) -> str:
        date = meta.date or time.strftime("%Y-%m-%d", time.localtime(time.time()))
        subject = meta.subject or "subject"
        # P24/P26: dual mode carries both operators; the electrode segment is
        # included ONLY when a hybrid is present (electrode non-empty) — a
        # plain single headband never shows a bare "na".
        head = f"{subject}_{meta.subject_b}" if meta.subject_b else subject
        electrode_seg = f"{meta.electrode}_" if meta.electrode else ""
        return (
            f"{head}_s{meta.session_no}_{meta.metric}_{meta.device_mode}_"
            f"{electrode_seg}{date}_{int(time.time())}"
        )

    def _write_session_json(self) -> None:
        assert self._meta is not None and self._session_dir is not None
        payload = {
            "session_id": self._session_id,
            # P20: meta = hand-filled operator fields only.
            "meta": {
                "subject": self._meta.subject,
                "subject_b": self._meta.subject_b,   # P24: device B (dual mode)
                "role": self._meta.role,
                "session_no": self._meta.session_no,
                "electrode": self._meta.electrode,
                "date": self._meta.date,
            },
            # P20: system = the ACTUAL runtime config at configure time
            # (metric/device_mode/roles/devices) — the label truth source.
            "system": self._system_summary,
            "protocol": {
                "shuffle": self._shuffle,
                "seed": self._seed,
                "prompt_sec": self._prompt_sec,
                "n_trials": len(self._trials),
            },
            "trials": [trial_dict(t) for t in self._trials],
        }
        (self._session_dir / "session.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _open_files_locked(self) -> None:
        assert self._session_dir is not None
        self._labels_fh = (self._session_dir / "labels.csv").open("w", newline="", encoding="utf-8")
        self._labels_writer = csv.DictWriter(self._labels_fh, fieldnames=LABELS_CSV_COLUMNS)
        self._labels_writer.writeheader()
        self._trials_fh = (self._session_dir / "trials.csv").open("w", newline="", encoding="utf-8")
        self._trials_writer = csv.DictWriter(self._trials_fh, fieldnames=TRIALS_CSV_COLUMNS)
        self._trials_writer.writeheader()

    def _close_files_locked(self) -> None:
        for fh in (self._labels_fh, self._trials_fh):
            if fh is not None:
                try:
                    fh.close()
                except Exception:
                    pass
        self._labels_fh = None
        self._trials_fh = None
        self._labels_writer = None
        self._trials_writer = None

    # ── operator control ─────────────────────────────────────────────────

    def start(self) -> bool:
        """Begin the trial sequence at trial 0 (prompt phase, E4 label)."""
        with self._lock:
            if not self._trials or self._phase not in (PHASE_IDLE, PHASE_DONE):
                return False
            self._trial_idx = 0
            now = self._clock()
            self._begin_prompt_locked(0, now)
            return True

    def pause(self) -> None:
        with self._lock:
            if self._phase not in (PHASE_PROMPT, PHASE_TRIAL):
                return
            # Remember BOTH the phase and the remaining seconds — the wall
            # clock keeps moving during the pause, so the deadline can't be
            # re-derived from the stale _phase_until later.
            self._paused_from = self._phase
            self._paused_remaining = max(0.0, self._phase_until - self._clock())
            self._phase = PHASE_PAUSED

    def resume(self) -> None:
        with self._lock:
            if self._phase != PHASE_PAUSED:
                return
            self._phase = self._paused_from
            self._phase_until = self._clock() + self._paused_remaining

    def reset(self) -> None:
        with self._lock:
            self._phase = PHASE_IDLE
            self._trial_idx = 0
            self._samples = []
            self._prev_steer = {}

    # ── phase machine (lazy, wall-clock derived) ─────────────────────────

    def _begin_prompt_locked(self, idx: int, now: float) -> None:
        self._phase = PHASE_PROMPT
        self._phase_until = now + self._prompt_sec
        self._record_label_locked(idx, now)  # E4: truth written at prompt entry

    def _begin_trial_locked(self, idx: int, now: float) -> None:
        self._phase = PHASE_TRIAL
        self._trial_start = now
        self._phase_until = now + self._trials[idx].duration_sec

    def _end_trial_locked(self, now: float) -> None:
        """P43: a trial ends straight into the NEXT trial's Get-ready prompt —
        there is no separate rest/inter-trial phase any more (one countdown
        between trials, the configurable prompt). The last trial → done."""
        self._trial_end = now
        self._write_trial_locked(now)          # flush the finished trial
        nxt = self._trial_idx + 1
        if nxt >= len(self._trials):
            self._phase = PHASE_DONE
            return
        self._trial_idx = nxt
        self._begin_prompt_locked(nxt, now)

    def _advance(self, now: float) -> None:
        with self._lock:
            # Loop so a single call collapses any number of due transitions —
            # a long gap (test clock jump / frontend back from sleep) still
            # lands on the correct phase. Paused returns immediately.
            while True:
                if self._phase == PHASE_PAUSED:
                    return
                if self._phase == PHASE_PROMPT and now >= self._phase_until:
                    self._begin_trial_locked(self._trial_idx, now)
                elif self._phase == PHASE_TRIAL and now >= self._phase_until:
                    self._end_trial_locked(now)   # → next prompt (or done)
                else:
                    return

    def state(self) -> dict:
        """Frontend view (E3): phase, current target, countdown, progress."""
        now = self._clock()
        self._advance(now)
        with self._lock:
            if not self._trials:
                return {"configured": False, "phase": PHASE_IDLE, "session_id": "", "n_trials": 0}
            trial = self._trials[self._trial_idx] if self._trial_idx < len(self._trials) else None
            remaining = 0.0
            if self._phase in (PHASE_PROMPT, PHASE_TRIAL):
                remaining = max(0.0, self._phase_until - now)
            return {
                "configured": True,
                "session_id": self._session_id,
                "phase": self._phase,
                "trial_idx": self._trial_idx,
                "n_trials": len(self._trials),
                "target": (
                    {"a_state": trial.a_state, "b_state": trial.b_state, "b_direction": trial.b_direction}
                    if trial is not None else None
                ),
                "remaining_sec": round(remaining, 2),
                # P29②: absolute wall-clock END timestamp (ms) of the current
                # phase, so the frontend can render a SMOOTH countdown (ticks
                # ~200 ms, integer second changes exactly 1 s apart) instead of
                # jittering on the 500 ms state poll. Default clock is
                # time.time (epoch s); *1000 aligns with browser Date.now().
                "end_ts_ms": int(self._phase_until * 1000)
                if self._phase in (PHASE_PROMPT, PHASE_TRIAL) else 0,
                "trial_elapsed": round((now - self._trial_start), 2) if self._phase == PHASE_TRIAL else 0.0,
            }

    # ── recording (E1) ───────────────────────────────────────────────────

    def on_frame(self, frame: dict) -> None:
        """Record one analysis frame while a trial is running (E1).

        ``frame`` is the RAW analysis JSON from the RosBridge handler hook:
        keys ts/source/role/metrics/features/intents/command_linear_x/
        command_angular_z/steer_direction (+ optional cmd_vel_ts).
        """
        now = self._clock()
        self._advance(now)
        with self._lock:
            if self._phase != PHASE_TRIAL or not self._trials:
                return
            trial = self._trials[self._trial_idx]
            intents = frame.get("intents") or {}
            metrics = frame.get("metrics") or {}
            features = frame.get("features") or {}
            alpha = float(metrics.get("alpha", 0.0))
            theta = float(metrics.get("theta", 0.0))
            beta = float(metrics.get("beta", 0.0))
            tbr = float(features.get("theta_beta") or (theta / beta if beta > 0 else 0.0))
            ei = float(features.get("beta_alpha_theta") or (beta / (alpha + theta) if (alpha + theta) > 0 else 0.0))

            role = str(frame.get("role", "speed"))
            steer_dir = int(frame.get("steer_direction", 0))
            prev = self._prev_steer.get(role)
            is_blink = prev is not None and prev != 0 and steer_dir != prev
            self._prev_steer[role] = steer_dir

            frame_ts = float(frame.get("ts", now))
            cmd_vel_ts = float(frame.get("cmd_vel_ts") or now)
            row = {
                "trial_idx": self._trial_idx,
                "a_state": trial.a_state,
                "b_state": trial.b_state,
                "b_direction": trial.b_direction,
                "trial_start_ts": round(self._trial_start, 6),
                "trial_end_ts": "",
                "row_ts": round(now, 6),
                "frame_ts": round(frame_ts, 6),
                "cmd_vel_ts": round(cmd_vel_ts, 6),
                "source": str(frame.get("source", "")),
                "role": role,
                "alpha": round(alpha, 6),
                "theta": round(theta, 6),
                "beta": round(beta, 6),
                "tbr": round(tbr, 6),
                "ei": round(ei, 6),
                "speed_intent": round(float(intents.get("speed_intent", 0.5)), 6),
                "steer_intent": round(float(intents.get("steer_intent", 0.5)), 6),
                "steer_direction": steer_dir,
                "cmd_lin": round(float(frame.get("command_linear_x", 0.0)), 6),
                "cmd_ang": round(float(frame.get("command_angular_z", 0.0)), 6),
                "is_blink": 1 if is_blink else 0,
                "latency_ms": round((now - cmd_vel_ts) * 1000.0, 3),
            }
            self._samples.append(row)

    def _record_label_locked(self, idx: int, now: float) -> None:
        if self._labels_writer is None:
            return
        trial = self._trials[idx]
        self._prompt_ts = now
        self._labels_writer.writerow({
            "trial_idx": idx,
            "phase": PHASE_PROMPT,
            "wall_ts": round(now, 6),
            "a_state": trial.a_state,
            "b_state": trial.b_state,
            "b_direction": trial.b_direction,
        })
        if self._labels_fh is not None:
            self._labels_fh.flush()

    def _write_trial_locked(self, now: float) -> None:
        """Flush the finished trial: per-trial CSV + trials.csv summary row."""
        if self._session_dir is None:
            return
        trial = self._trials[self._trial_idx]
        trial_end = round(now, 6)
        for row in self._samples:
            row["trial_end_ts"] = trial_end

        path = self._session_dir / f"trial_{self._trial_idx:03d}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=TRIAL_CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(self._samples)

        if self._trials_writer is not None:
            n = len(self._samples)
            self._trials_writer.writerow({
                "trial_idx": self._trial_idx,
                "a_state": trial.a_state,
                "b_state": trial.b_state,
                "b_direction": trial.b_direction,
                "prompt_ts": round(self._prompt_ts, 6),
                "start_ts": round(self._trial_start, 6),
                "end_ts": trial_end,
                "duration_sec": round(now - self._trial_start, 6),
                "n_samples": n,
                "mean_alpha": round(_mean([float(s["alpha"]) for s in self._samples]), 6),
                "mean_tbr": round(_mean([float(s["tbr"]) for s in self._samples]), 6),
                "mean_ei": round(_mean([float(s["ei"]) for s in self._samples]), 6),
                "blink_count": sum(1 for s in self._samples if s["is_blink"]),
            })
            if self._trials_fh is not None:
                self._trials_fh.flush()

        self._samples = []

    def close(self) -> None:
        with self._lock:
            self._close_files_locked()


def load_protocol(path: str | Path) -> dict:
    """Parse a protocol config file → ``{"trials", "shuffle", "seed", "prompt_sec"}``.

    Format::
        {"prompt_sec": 3.0, "shuffle": "balanced", "seed": null,
         "trials": [{"a_state": "attention", "b_state": "rest",
                     "b_direction": "left", "duration_sec": 20.0, "rest_sec": 10.0}]}
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_trials = data.get("trials")
    if not isinstance(raw_trials, list) or not raw_trials:
        raise ValueError(f"protocol {path!r} must define a non-empty 'trials' list")
    trials = [TrialSpec(**t) for t in raw_trials]
    shuffle = str(data.get("shuffle", "none"))
    if shuffle not in ("none", "random", "balanced"):
        raise ValueError(f"protocol shuffle must be none/random/balanced, got {shuffle!r}")
    return {
        "trials": trials,
        "shuffle": shuffle,
        "seed": data.get("seed"),
        "prompt_sec": float(data.get("prompt_sec", PROMPT_SEC)),
    }


DEFAULT_PROTOCOL = Path(__file__).resolve().parent / "protocol.json"
