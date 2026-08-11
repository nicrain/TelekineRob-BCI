import shlex

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


# ---------------------------------------------------------------------------
# P9 — venv python for eeg_control_node
# ---------------------------------------------------------------------------


def _venv_export(venv_bin):
    return f"export PATH={shlex.quote(str(venv_bin))}:\"$PATH\""


def test_venv_bin_path_prefers_repo_root_venv(tmp_path, monkeypatch):
    """Repo-root .venv (launcher backend_cmd default) wins over backend-local."""
    repo_bin = tmp_path / ".venv" / "bin"
    backend_bin = tmp_path / "web_gui" / "backend" / ".venv" / "bin"
    repo_bin.mkdir(parents=True)
    backend_bin.mkdir(parents=True)
    monkeypatch.setattr(command_runner, "_repo_root", lambda: tmp_path)

    assert command_runner._venv_bin_path() == repo_bin


def test_venv_bin_path_falls_back_to_backend_venv(tmp_path, monkeypatch):
    """Documented deployment (launcher README): backend-local .venv is used
    when the repo-root .venv is absent."""
    backend_bin = tmp_path / "web_gui" / "backend" / ".venv" / "bin"
    backend_bin.mkdir(parents=True)
    monkeypatch.setattr(command_runner, "_repo_root", lambda: tmp_path)

    assert command_runner._venv_bin_path() == backend_bin


def test_venv_bin_path_none_when_no_venv(tmp_path, monkeypatch):
    monkeypatch.setattr(command_runner, "_repo_root", lambda: tmp_path)

    assert command_runner._venv_bin_path() is None


def test_source_prefix_puts_venv_export_last():
    """P9: the venv export must come after the ROS sources — last prepend is
    front of PATH, so `env python3` resolves the venv python3 (pylsl), not
    anything /opt/ros or system put ahead."""
    prefix = command_runner._source_prefix()
    venv_bin = command_runner._venv_bin_path()
    assert venv_bin is not None  # repo ships a venv today
    venv_export = _venv_export(venv_bin)

    assert venv_export in prefix
    assert prefix.index(venv_export) > prefix.index("source /opt/ros/kilted/setup.bash")


def test_source_prefix_without_venv_omits_venv_export(monkeypatch):
    """No venv present → no export line, ROS chain intact (no short-circuit)."""
    monkeypatch.setattr(command_runner, "_venv_bin_path", lambda: None)

    prefix = command_runner._source_prefix()

    assert "source /opt/ros/kilted/setup.bash" in prefix
    assert ".venv" not in prefix


def test_load_ros_env_captures_venv_in_path(monkeypatch):
    """P9 core: the bash -lc chain the backend actually runs must land the
    venv bin dir in the captured env's PATH. macOS has no /opt/ros/kilted, so
    run exactly the venv segment the real _source_prefix() emits — the same
    line that follows the ROS sources on the device."""
    venv_bin = command_runner._venv_bin_path()
    assert venv_bin is not None
    monkeypatch.setattr(command_runner, "_ros_env_cache", None)
    monkeypatch.setattr(
        command_runner, "_source_prefix",
        lambda: _venv_export(venv_bin),
    )

    env = command_runner._load_ros_env()

    path_parts = env["PATH"].split(":")
    assert str(venv_bin) in path_parts
    assert path_parts[0] == str(venv_bin)  # wins over ROS/system for env python3
