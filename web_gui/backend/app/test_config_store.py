from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app import config_store


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def test_patch_config_persists_to_yaml(monkeypatch, tmp_path: Path):
    launch_path = tmp_path / "launch_args.yaml"
    eeg_path = tmp_path / "eeg_control_node.params.yaml"
    eeg2_path = tmp_path / "eeg_control_node.eeg2.params.yaml"

    _write_yaml(
        launch_path,
        {
            "use_sim": True,
            "use_gui": True,
            "run_eeg": False,
        },
    )
    _write_yaml(
        eeg_path,
        {
            "/**": {
                "ros__parameters": {
                    "input": "mock",
                    "policy": "tbr",
                    "lsl_stream_type": "EEG",
                    "lsl_timeout": 8.0,
                    "max_forward_speed": 0.2,
                    "reverse_speed": -0.15,
                    "turn_forward_speed": 0.1,
                    "turn_angular_speed": 1.2,
                    "steer_deadzone": 0.1,
                    "line_mode": "",
                }
            }
        },
    )

    monkeypatch.setattr(config_store, "_LAUNCH_YAML", launch_path)
    monkeypatch.setattr(config_store, "_EEG_YAML", eeg_path)
    monkeypatch.setattr(config_store, "_EEG2_YAML", eeg2_path)

    config_store.init_store()
    config_store.patch_config(
        {
            "launch": {"run_eeg": True},
            "eeg": {"lsl_source_id": "gtec_bci_core4"},
        }
    )

    launch_loaded = yaml.safe_load(launch_path.read_text(encoding="utf-8"))
    eeg_loaded = yaml.safe_load(eeg_path.read_text(encoding="utf-8"))

    assert launch_loaded["run_eeg"] is True
    assert eeg_loaded["/**"]["ros__parameters"]["lsl_source_id"] == "gtec_bci_core4"
    # device 2 is disabled by default → eeg2 stays None, file holds safe defaults
    assert launch_loaded["run_eeg2"] is False
    eeg2_params = yaml.safe_load(eeg2_path.read_text(encoding="utf-8"))["/**"]["ros__parameters"]
    assert eeg2_params["role"] == "steering"
    assert eeg2_params["calibrate"] is False


def test_patch_eeg2_persists_to_own_file(monkeypatch, tmp_path: Path):
    launch_path = tmp_path / "launch_args.yaml"
    eeg_path = tmp_path / "eeg_control_node.params.yaml"
    eeg2_path = tmp_path / "eeg_control_node.eeg2.params.yaml"

    _write_yaml(launch_path, {"use_sim": True, "run_eeg": False})
    _write_yaml(eeg_path, {"/**": {"ros__parameters": {"role": "speed"}}})

    monkeypatch.setattr(config_store, "_LAUNCH_YAML", launch_path)
    monkeypatch.setattr(config_store, "_EEG_YAML", eeg_path)
    monkeypatch.setattr(config_store, "_EEG2_YAML", eeg2_path)

    config_store.init_store()
    config_store.patch_config(
        {
            "eeg": {"role": "speed", "lsl_source_id": "gtec_hybrid_black"},
            "eeg2": {
                "role": "steering",
                "policy": "alpha",
                "calibrate": True,
                "calib_offset": 0.5,
                "calib_scale": 2.0,
                "lsl_source_id": "gtec_bci_core4",
            },
        }
    )

    launch_loaded = yaml.safe_load(launch_path.read_text(encoding="utf-8"))
    params = yaml.safe_load(eeg2_path.read_text(encoding="utf-8"))["/**"]["ros__parameters"]

    assert launch_loaded["run_eeg2"] is True
    assert launch_loaded["eeg2"] is None  # legacy block superseded
    assert params["role"] == "steering"
    assert params["policy"] == "alpha"
    assert params["calibrate"] is True
    assert params["calib_offset"] == 0.5
    assert params["calib_scale"] == 2.0
    assert params["lsl_source_id"] == "gtec_bci_core4"
    assert params["cmd_topic"] == "/eeg_cmd_vel/steering"
    assert params["analysis_topic"] == "/eeg_analysis/steering"
    assert params["csv_path"] == "/tmp/thymio_eeg_log_eeg2.csv"


def test_reload_round_trips_eeg2(monkeypatch, tmp_path: Path):
    launch_path = tmp_path / "launch_args.yaml"
    eeg_path = tmp_path / "eeg_control_node.params.yaml"
    eeg2_path = tmp_path / "eeg_control_node.eeg2.params.yaml"

    _write_yaml(launch_path, {"use_sim": True, "run_eeg": False})
    _write_yaml(eeg_path, {"/**": {"ros__parameters": {"role": "speed"}}})

    monkeypatch.setattr(config_store, "_LAUNCH_YAML", launch_path)
    monkeypatch.setattr(config_store, "_EEG_YAML", eeg_path)
    monkeypatch.setattr(config_store, "_EEG2_YAML", eeg2_path)

    config_store.init_store()
    config_store.patch_config({"eeg2": {"role": "steering", "calib_offset": 1.25}})

    config_store.init_store()  # simulate backend restart / reload from disk
    env = config_store.get_config_envelope()

    assert env.config.eeg2 is not None
    assert env.config.eeg2.role == "steering"
    assert env.config.eeg2.calib_offset == 1.25
    assert env.config.eeg2.calib_scale == 1.0
    assert "eeg2" in env.source_files


def test_run_eeg2_false_resets_eeg2_to_none(monkeypatch, tmp_path: Path):
    launch_path = tmp_path / "launch_args.yaml"
    eeg_path = tmp_path / "eeg_control_node.params.yaml"
    eeg2_path = tmp_path / "eeg_control_node.eeg2.params.yaml"

    _write_yaml(
        launch_path,
        {"use_sim": True, "run_eeg": False, "run_eeg2": True},
    )
    _write_yaml(eeg_path, {"/**": {"ros__parameters": {"role": "speed"}}})
    _write_yaml(
        eeg2_path,
        {"/**": {"ros__parameters": {"role": "steering", "calibrate": True}}},
    )

    monkeypatch.setattr(config_store, "_LAUNCH_YAML", launch_path)
    monkeypatch.setattr(config_store, "_EEG_YAML", eeg_path)
    monkeypatch.setattr(config_store, "_EEG2_YAML", eeg2_path)

    config_store.init_store()
    assert config_store.get_config_envelope().config.eeg2 is not None

    config_store.patch_config({"eeg2": None})  # frontend disables device 2

    env = config_store.get_config_envelope(reload=True)
    assert env.config.eeg2 is None
    launch_loaded = yaml.safe_load(launch_path.read_text(encoding="utf-8"))
    assert launch_loaded["run_eeg2"] is False
    # file not deleted — reset to safe defaults
    params = yaml.safe_load(eeg2_path.read_text(encoding="utf-8"))["/**"]["ros__parameters"]
    assert params["calibrate"] is False
    assert params["role"] == "steering"


def test_legacy_eeg2_block_migrates_to_file(monkeypatch, tmp_path: Path):
    launch_path = tmp_path / "launch_args.yaml"
    eeg_path = tmp_path / "eeg_control_node.params.yaml"
    eeg2_path = tmp_path / "eeg_control_node.eeg2.params.yaml"

    # run_eeg2 enabled but device-2 file absent → legacy launch_args block seeds it
    _write_yaml(
        launch_path,
        {
            "use_sim": True,
            "run_eeg2": True,
            "eeg2": {"role": "steering", "policy": "alpha", "lsl_source_id": "gtec_bci_core4"},
        },
    )
    _write_yaml(eeg_path, {"/**": {"ros__parameters": {"role": "speed"}}})

    monkeypatch.setattr(config_store, "_LAUNCH_YAML", launch_path)
    monkeypatch.setattr(config_store, "_EEG_YAML", eeg_path)
    monkeypatch.setattr(config_store, "_EEG2_YAML", eeg2_path)

    config_store.init_store()
    env = config_store.get_config_envelope()

    assert env.config.eeg2 is not None
    assert env.config.eeg2.role == "steering"
    assert env.config.eeg2.policy == "alpha"
    assert env.config.eeg2.lsl_source_id == "gtec_bci_core4"

    params = yaml.safe_load(eeg2_path.read_text(encoding="utf-8"))["/**"]["ros__parameters"]
    assert params["role"] == "steering"
    assert params["lsl_source_id"] == "gtec_bci_core4"


def test_motion_changes_reach_eeg2_file(monkeypatch, tmp_path: Path):
    """O2: device-2 params file must mirror cfg.motion, not frozen defaults."""
    launch_path = tmp_path / "launch_args.yaml"
    eeg_path = tmp_path / "eeg_control_node.params.yaml"
    eeg2_path = tmp_path / "eeg_control_node.eeg2.params.yaml"

    _write_yaml(launch_path, {"use_sim": True, "run_eeg": False})
    _write_yaml(eeg_path, {"/**": {"ros__parameters": {"role": "speed"}}})

    monkeypatch.setattr(config_store, "_LAUNCH_YAML", launch_path)
    monkeypatch.setattr(config_store, "_EEG_YAML", eeg_path)
    monkeypatch.setattr(config_store, "_EEG2_YAML", eeg2_path)

    config_store.init_store()
    config_store.patch_config(
        {
            "eeg": {"role": "speed"},
            "eeg2": {"role": "steering"},
            "motion": {"turn_angular_speed": 2.4, "max_forward_speed": 0.35},
        }
    )

    params = yaml.safe_load(eeg2_path.read_text(encoding="utf-8"))["/**"]["ros__parameters"]
    assert params["turn_angular_speed"] == 2.4
    assert params["max_forward_speed"] == 0.35


def test_device1_invalid_role_rejected_on_load(monkeypatch, tmp_path: Path):
    """O25: device-1 config must go through model_validate, so an invalid
    role (silently accepted before) now fails fast like device 2."""
    launch_path = tmp_path / "launch_args.yaml"
    eeg_path = tmp_path / "eeg_control_node.params.yaml"
    eeg2_path = tmp_path / "eeg_control_node.eeg2.params.yaml"

    _write_yaml(launch_path, {"use_sim": True, "run_eeg": False})
    _write_yaml(eeg_path, {"/**": {"ros__parameters": {"role": "sideways", "policy": "tbr"}}})

    monkeypatch.setattr(config_store, "_LAUNCH_YAML", launch_path)
    monkeypatch.setattr(config_store, "_EEG_YAML", eeg_path)
    monkeypatch.setattr(config_store, "_EEG2_YAML", eeg2_path)

    with pytest.raises(ValidationError):
        config_store.init_store()


def test_motion_invalid_line_mode_rejected_on_load(monkeypatch, tmp_path: Path):
    """N3: motion.line_mode is a Literal and must fail fast like O25."""
    launch_path = tmp_path / "launch_args.yaml"
    eeg_path = tmp_path / "eeg_control_node.params.yaml"
    eeg2_path = tmp_path / "eeg_control_node.eeg2.params.yaml"

    _write_yaml(launch_path, {"use_sim": True, "run_eeg": False})
    _write_yaml(
        eeg_path,
        {"/**": {"ros__parameters": {"role": "speed", "line_mode": "sideways"}}},
    )

    monkeypatch.setattr(config_store, "_LAUNCH_YAML", launch_path)
    monkeypatch.setattr(config_store, "_EEG_YAML", eeg_path)
    monkeypatch.setattr(config_store, "_EEG2_YAML", eeg2_path)

    with pytest.raises(ValidationError):
        config_store.init_store()
