import pytest

import app.command_runner as command_runner
from app.command_runner import _build_launch_command, cleanup_residual_processes, start_system, stop_system
from app.models import AppConfig, EegConfig2


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


# ---------------------------------------------------------------------------
# allow_real gate (default ON — opt out with =false) — start / stop / cleanup
# must be symmetric
# ---------------------------------------------------------------------------


def test_real_commands_default_true(monkeypatch):
    monkeypatch.delenv("WEB_GUI_ALLOW_REAL_COMMANDS", raising=False)
    assert command_runner._real_commands_enabled() is True


def test_real_commands_enabled_when_env_set(monkeypatch):
    monkeypatch.setenv("WEB_GUI_ALLOW_REAL_COMMANDS", "true")
    assert command_runner._real_commands_enabled() is True


def test_real_commands_disabled_when_env_false(monkeypatch):
    monkeypatch.setenv("WEB_GUI_ALLOW_REAL_COMMANDS", "false")
    assert command_runner._real_commands_enabled() is False


def test_start_system_dry_run_when_explicitly_false(monkeypatch):
    monkeypatch.setenv("WEB_GUI_ALLOW_REAL_COMMANDS", "false")
    result = start_system(AppConfig(), dry_run=False)
    assert result.dry_run is True
    assert "Dry-run" in result.detail


def test_start_system_default_true_reaches_spawn(monkeypatch):
    """With the env unset (default true) a non-dry start must reach the
    spawn path instead of being short-circuited to dry-run."""
    monkeypatch.delenv("WEB_GUI_ALLOW_REAL_COMMANDS", raising=False)
    cfg = AppConfig()
    cfg.launch.use_sim = False  # real robot, not Gazebo
    spawned: list[list[str]] = []
    monkeypatch.setattr(command_runner, "_spawn_ros_command", spawned.append)
    monkeypatch.setattr(command_runner, "_stop_runtime_processes", lambda: None)
    monkeypatch.setattr(command_runner, "set_runtime_state", lambda *_: None)

    result = start_system(cfg, dry_run=False)

    assert result.dry_run is False
    assert "Real Thymio system started" in result.detail
    assert spawned  # the launch command was actually handed to spawn


def test_stop_system_mock_mode_does_not_pkill(monkeypatch):
    monkeypatch.setenv("WEB_GUI_ALLOW_REAL_COMMANDS", "false")
    killed: list[bool] = []
    monkeypatch.setattr(command_runner, "_kill_ros_processes", lambda: killed.append(True))
    monkeypatch.setattr(command_runner, "_send_stop_to_thymio", lambda: None)
    monkeypatch.setattr(command_runner, "_stop_runtime_processes", lambda: None)
    monkeypatch.setattr(command_runner, "set_runtime_state", lambda *_: None)

    result = stop_system(dry_run=False)

    assert killed == []
    assert "mock mode" in result.detail.lower()


def test_stop_system_real_mode_pkills(monkeypatch):
    monkeypatch.setenv("WEB_GUI_ALLOW_REAL_COMMANDS", "true")
    killed: list[bool] = []
    monkeypatch.setattr(command_runner, "_kill_ros_processes", lambda: killed.append(True))
    monkeypatch.setattr(command_runner, "_send_stop_to_thymio", lambda: None)
    monkeypatch.setattr(command_runner, "_stop_runtime_processes", lambda: None)
    monkeypatch.setattr(command_runner, "set_runtime_state", lambda *_: None)

    stop_system(dry_run=False)

    assert killed == [True]


def test_cleanup_residual_skips_in_mock_mode(monkeypatch):
    monkeypatch.setenv("WEB_GUI_ALLOW_REAL_COMMANDS", "false")
    killed: list[bool] = []
    monkeypatch.setattr(command_runner, "_kill_ros_processes", lambda: killed.append(True))

    detail = cleanup_residual_processes()

    assert "skipped" in detail
    assert killed == []


# ---------------------------------------------------------------------------
# Dual-device launch args (design §5.4.3)
# ---------------------------------------------------------------------------


def test_launch_command_includes_dual_device_args():
    cfg = AppConfig()
    cfg.launch.run_eeg = True
    cfg.eeg.role = "speed"
    cfg.eeg2 = EegConfig2(role="steering", input="lsl")

    command = " ".join(_build_launch_command(cfg))

    assert "run_eeg2:=true" in command
    assert "eeg2_role:=steering" in command
    assert "eeg2_input:=lsl" in command


def test_launch_command_single_device_omits_dual_args():
    cfg = AppConfig()
    cfg.launch.run_eeg = True

    command = " ".join(_build_launch_command(cfg))

    assert "run_eeg2:=" not in command
    assert "eeg2_role:=" not in command


def test_launch_command_eeg2_ignored_when_run_eeg_false():
    cfg = AppConfig()  # run_eeg defaults to False
    cfg.eeg2 = EegConfig2(role="steering")

    command = " ".join(_build_launch_command(cfg))

    assert "run_eeg2:=" not in command


def test_start_system_rejects_eeg2_without_run_eeg():
    cfg = AppConfig()
    cfg.eeg2 = EegConfig2(role="steering")

    with pytest.raises(ValueError, match="eeg2 is configured"):
        start_system(cfg, dry_run=True)
