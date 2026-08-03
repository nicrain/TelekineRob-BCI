import app.command_runner as command_runner
from app.command_runner import _build_launch_command, cleanup_residual_processes, start_system, stop_system
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


# ---------------------------------------------------------------------------
# allow_real gate (default OFF) — start / stop / cleanup must be symmetric
# ---------------------------------------------------------------------------


def test_real_commands_default_false(monkeypatch):
    monkeypatch.delenv("WEB_GUI_ALLOW_REAL_COMMANDS", raising=False)
    assert command_runner._real_commands_enabled() is False


def test_real_commands_enabled_when_env_set(monkeypatch):
    monkeypatch.setenv("WEB_GUI_ALLOW_REAL_COMMANDS", "true")
    assert command_runner._real_commands_enabled() is True


def test_start_system_dry_run_when_not_allowed(monkeypatch):
    monkeypatch.delenv("WEB_GUI_ALLOW_REAL_COMMANDS", raising=False)
    result = start_system(AppConfig(), dry_run=False)
    assert result.dry_run is True
    assert "Dry-run" in result.detail


def test_stop_system_mock_mode_does_not_pkill(monkeypatch):
    monkeypatch.delenv("WEB_GUI_ALLOW_REAL_COMMANDS", raising=False)
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
    monkeypatch.delenv("WEB_GUI_ALLOW_REAL_COMMANDS", raising=False)
    killed: list[bool] = []
    monkeypatch.setattr(command_runner, "_kill_ros_processes", lambda: killed.append(True))

    detail = cleanup_residual_processes()

    assert "skipped" in detail
    assert killed == []
