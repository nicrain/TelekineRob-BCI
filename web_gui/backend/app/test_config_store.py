from pathlib import Path

import yaml

from app import config_store


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def test_patch_config_persists_to_yaml(monkeypatch, tmp_path: Path):
    launch_path = tmp_path / "launch_args.yaml"
    eeg_path = tmp_path / "eeg_control_node.params.yaml"

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
