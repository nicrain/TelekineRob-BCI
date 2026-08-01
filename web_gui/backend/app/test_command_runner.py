from app.command_runner import _build_launch_command
from app.models import AppConfig


def test_launch_command_includes_run_eeg_and_device():
    cfg = AppConfig()
    cfg.launch.run_eeg = True
    cfg.launch.device = "bci-core-4"
    cfg.eeg.role = "steering"
    cfg.eeg.policy = "tbr"

    command = " ".join(_build_launch_command(cfg))

    assert "ros2 launch thymio_control experiment_core.launch.py" in command
    assert "run_eeg:=true" in command
    assert "role:=steering" in command


def test_launch_command_without_eeg_omits_role_and_device():
    cfg = AppConfig()
    cfg.launch.run_eeg = False

    command = " ".join(_build_launch_command(cfg))

    assert "run_eeg:=false" in command
    assert "role:=" not in command
    assert "policy:=" not in command
    assert "device:=" not in command
