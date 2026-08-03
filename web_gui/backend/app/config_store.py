from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

import yaml

from .models import AppConfig, ConfigEnvelope, EegConfig, EegConfig2, MotionConfig


_REPO_ROOT = Path(__file__).resolve().parents[3]
_LAUNCH_YAML = _REPO_ROOT / "thymio_control/config/launch_args.yaml"
_EEG_YAML = _REPO_ROOT / "thymio_control/config/eeg_control_node.params.yaml"
_EEG2_YAML = _REPO_ROOT / "thymio_control/config/eeg_control_node.eeg2.params.yaml"

_lock = Lock()
_current = AppConfig()


def _safe_load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if isinstance(data, dict):
        return data
    return {}


def _load_defaults() -> AppConfig:
    cfg = AppConfig()

    launch_cfg = _safe_load(_LAUNCH_YAML)
    cfg.launch.use_sim = bool(launch_cfg.get("use_sim", cfg.launch.use_sim))
    cfg.launch.use_gui = bool(launch_cfg.get("use_gui", cfg.launch.use_gui))
    cfg.launch.run_eeg = bool(launch_cfg.get("run_eeg", cfg.launch.run_eeg))
    cfg.launch.run_eeg2 = bool(launch_cfg.get("run_eeg2", cfg.launch.run_eeg2))
    cfg.launch.run_rviz = bool(launch_cfg.get("run_rviz", cfg.launch.run_rviz))
    cfg.launch.device = str(launch_cfg.get("device", cfg.launch.device))

    eeg_root = _safe_load(_EEG_YAML)
    ros_params = eeg_root.get("/**", {}).get("ros__parameters", {})
    # Build device 1 through model_validate so role/policy are checked against
    # their Literal types (fail-fast on invalid YAML), matching device 2.
    cfg.eeg = EegConfig.model_validate(
        {
            "input": str(ros_params.get("input", cfg.eeg.input)),
            "policy": str(ros_params.get("policy", cfg.eeg.policy)),
            "calibrate": bool(ros_params.get("calibrate", cfg.eeg.calibrate)),
            "calib_offset": float(ros_params.get("calib_offset", cfg.eeg.calib_offset)),
            "calib_scale": float(ros_params.get("calib_scale", cfg.eeg.calib_scale)),
            "lsl_stream_type": str(ros_params.get("lsl_stream_type", cfg.eeg.lsl_stream_type)),
            "lsl_timeout": float(ros_params.get("lsl_timeout", cfg.eeg.lsl_timeout)),
            "lsl_source_id": str(ros_params.get("lsl_source_id", cfg.eeg.lsl_source_id)),
            "role": str(ros_params.get("role", cfg.eeg.role)),
        }
    )

    # Device 2 is gated by the launch-level run_eeg2 switch; its own param
    # file is the source of truth. A residual file is NOT honored when off.
    if cfg.launch.run_eeg2:
        cfg.eeg2 = _load_eeg2_config(launch_cfg)

    cfg.motion.max_forward_speed = float(ros_params.get("max_forward_speed", cfg.motion.max_forward_speed))
    cfg.motion.reverse_speed = float(ros_params.get("reverse_speed", cfg.motion.reverse_speed))
    cfg.motion.turn_forward_speed = float(ros_params.get("turn_forward_speed", cfg.motion.turn_forward_speed))
    cfg.motion.turn_angular_speed = float(ros_params.get("turn_angular_speed", cfg.motion.turn_angular_speed))
    cfg.motion.steer_deadzone = float(ros_params.get("steer_deadzone", cfg.motion.steer_deadzone))
    cfg.motion.line_mode = str(ros_params.get("line_mode", cfg.motion.line_mode))
    cfg.motion.line_pivot_gain = float(ros_params.get("line_pivot_gain", cfg.motion.line_pivot_gain))
    cfg.motion.line_spin_gain = float(ros_params.get("line_spin_gain", cfg.motion.line_spin_gain))

    return cfg


def _load_eeg2_config(launch_cfg: dict[str, Any]) -> EegConfig2:
    """Load device-2 config from its own param file.

    One-time migration: when the device-2 file is empty but launch_args still
    carries a legacy ``eeg2`` block, seed the file from it and return it.
    After that the legacy block is never read again (persist clears it).
    """
    eeg2_root = _safe_load(_EEG2_YAML)
    ros_params = eeg2_root.get("/**", {}).get("ros__parameters", {})
    if not ros_params:
        legacy = launch_cfg.get("eeg2")
        if isinstance(legacy, dict) and legacy:
            eeg2 = EegConfig2(
                input=str(legacy.get("input", "lsl")),
                role=str(legacy.get("role", "steering")),
                policy=str(legacy.get("policy", "tbr")),
                lsl_stream_type=str(legacy.get("lsl_stream_type", "EEG")),
                lsl_timeout=float(legacy.get("lsl_timeout", 8.0)),
                lsl_source_id=str(legacy.get("lsl_source_id", "")),
            )
            # Motion not available during load — seed defaults; the next
            # persist() rewrites with the real cfg.motion.
            _write_eeg2_params(eeg2, MotionConfig())
            return eeg2
    return EegConfig2(
        input=str(ros_params.get("input", "lsl")),
        role=str(ros_params.get("role", "steering")),
        policy=str(ros_params.get("policy", "tbr")),
        calibrate=bool(ros_params.get("calibrate", False)),
        calib_offset=float(ros_params.get("calib_offset", 0.0)),
        calib_scale=float(ros_params.get("calib_scale", 1.0)),
        lsl_stream_type=str(ros_params.get("lsl_stream_type", "EEG")),
        lsl_timeout=float(ros_params.get("lsl_timeout", 8.0)),
        lsl_source_id=str(ros_params.get("lsl_source_id", "")),
    )


def _write_eeg2_params(eeg2: EegConfig2, motion: MotionConfig) -> None:
    """Write the device-2 ROS params file (full block, deterministic).

    The file always exists — when device 2 is disabled it holds safe defaults.
    Motion params come from *motion* so UI changes (turn_angular_speed, etc.)
    reach device 2, not just device 1. ``cmd_topic`` / ``analysis_topic`` are
    derived from the role; launch overrides them anyway (fallback default).
    """
    _EEG2_YAML.parent.mkdir(parents=True, exist_ok=True)
    params = {
        "input": str(eeg2.input),
        "policy": str(eeg2.policy),
        "calibrate": bool(eeg2.calibrate),
        "calib_offset": float(eeg2.calib_offset),
        "calib_scale": float(eeg2.calib_scale),
        "lsl_stream_type": str(eeg2.lsl_stream_type),
        "lsl_timeout": float(eeg2.lsl_timeout),
        "lsl_source_id": str(eeg2.lsl_source_id),
        "role": str(eeg2.role),
        "cmd_topic": f"/eeg_cmd_vel/{eeg2.role}",
        "analysis_topic": f"/eeg_analysis/{eeg2.role}",
        "publish_hz": 20.0,
        "watchdog_sec": 0.5,
        "verbose": False,
        "analysis_verbose": False,
        "record_csv": False,
        "csv_path": "/tmp/thymio_eeg_log_eeg2.csv",
        "max_forward_speed": motion.max_forward_speed,
        "reverse_speed": motion.reverse_speed,
        "turn_forward_speed": motion.turn_forward_speed,
        "turn_angular_speed": motion.turn_angular_speed,
        "steer_deadzone": motion.steer_deadzone,
        "line_mode": motion.line_mode,
        "blink_holdoff_frames": 4,
        "blink_confirm_frames": 2,
    }
    payload = {"/**": {"ros__parameters": params}}
    with _EEG2_YAML.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=False)


def _persist_config(cfg: AppConfig) -> None:
    launch_payload = {
        "use_sim": bool(cfg.launch.use_sim),
        "use_gui": bool(cfg.launch.use_gui),
        "run_eeg": bool(cfg.launch.run_eeg),
        "run_eeg2": bool(cfg.eeg2 is not None),
        "run_rviz": bool(cfg.launch.run_rviz),
        "device": str(cfg.launch.device),
        "eeg_config_file": "eeg_control_node.params.yaml",
        "eeg2": None,  # legacy block superseded by the device-2 params file; clear explicitly
    }
    if _LAUNCH_YAML.exists():
        launch_payload = _deep_merge(_safe_load(_LAUNCH_YAML), launch_payload)

    eeg_payload = _safe_load(_EEG_YAML)
    ros_params = dict(eeg_payload.get("/**", {}).get("ros__parameters", {}))
    ros_params.update(
        {
            "input": str(cfg.eeg.input),
            "policy": str(cfg.eeg.policy),
            "calibrate": bool(cfg.eeg.calibrate),
            "calib_offset": float(cfg.eeg.calib_offset),
            "calib_scale": float(cfg.eeg.calib_scale),
            "lsl_stream_type": str(cfg.eeg.lsl_stream_type),
            "lsl_timeout": float(cfg.eeg.lsl_timeout),
            "lsl_source_id": str(cfg.eeg.lsl_source_id),
            "role": str(cfg.eeg.role),
            "max_forward_speed": float(cfg.motion.max_forward_speed),
            "reverse_speed": float(cfg.motion.reverse_speed),
            "turn_forward_speed": float(cfg.motion.turn_forward_speed),
            "turn_angular_speed": float(cfg.motion.turn_angular_speed),
            "steer_deadzone": float(cfg.motion.steer_deadzone),
            "line_mode": str(cfg.motion.line_mode),
            "line_pivot_gain": float(cfg.motion.line_pivot_gain),
            "line_spin_gain": float(cfg.motion.line_spin_gain),
        }
    )
    eeg_payload["/**"] = _deep_merge(eeg_payload.get("/**", {}), {"ros__parameters": ros_params})

    _LAUNCH_YAML.parent.mkdir(parents=True, exist_ok=True)
    _EEG_YAML.parent.mkdir(parents=True, exist_ok=True)
    with _LAUNCH_YAML.open("w", encoding="utf-8") as f:
        yaml.safe_dump(launch_payload, f, sort_keys=False, allow_unicode=False)
    with _EEG_YAML.open("w", encoding="utf-8") as f:
        yaml.safe_dump(eeg_payload, f, sort_keys=False, allow_unicode=False)
    # Device-2 file is always (re)written: safe defaults when disabled,
    # never deleted (avoid destructive operations).
    _write_eeg2_params(
        cfg.eeg2 if cfg.eeg2 is not None else EegConfig2(),
        cfg.motion,
    )


def init_store() -> None:
    global _current
    with _lock:
        _current = _load_defaults()


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _source_files() -> dict[str, str]:
    return {
        "launch": str(_LAUNCH_YAML),
        "eeg": str(_EEG_YAML),
        "eeg2": str(_EEG2_YAML),
    }


def get_config_envelope(*, reload: bool = False) -> ConfigEnvelope:
    global _current
    with _lock:
        if reload:
            _current = _load_defaults()
        snap = _current
    return ConfigEnvelope(config=snap, source_files=_source_files())


def _build_envelope(cfg: AppConfig) -> ConfigEnvelope:
    return ConfigEnvelope(config=cfg, source_files=_source_files())


def patch_config(patch: dict[str, Any]) -> ConfigEnvelope:
    global _current
    with _lock:
        merged = _deep_merge(_current.model_dump(), patch)
        _current = AppConfig.model_validate(merged)
        _persist_config(_current)
        snap = _current
    return _build_envelope(snap)
