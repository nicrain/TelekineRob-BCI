from pathlib import Path


def test_eeg_launch_params_include_tcp_control_mode():
    config_path = Path(__file__).resolve().parents[1] / "config" / "eeg_control_node.params.yaml"

    with config_path.open("r", encoding="utf-8") as handle:
        text = handle.read()

    assert "tcp_control_mode:" in text