from __future__ import annotations

import os
import shlex
import signal
import subprocess
from pathlib import Path
from typing import Any, Optional

from .models import AppConfig, CommandResult
from .ros_probe import set_runtime_state


_runtime_processes: list[subprocess.Popen[str]] = []
_ros_env_cache: Optional[dict[str, str]] = None


def _bool_str(v: bool) -> str:
    return "true" if v else "false"


def _build_launch_command(cfg: AppConfig) -> list[str]:
    launch = cfg.launch
    run_eeg = bool(launch.run_eeg)
    use_sim = bool(launch.use_sim)
    cmd = [
        "ros2", "launch", "thymio_control", "experiment_core.launch.py",
        f"use_sim:={_bool_str(use_sim)}",
        f"use_gui:={_bool_str(launch.use_gui)}",
        f"run_eeg:={_bool_str(run_eeg)}",
        # Web GUI teleop uses /ws/teleop (WebSocket → RosBridge → /cmd_vel),
        # not ros2 teleop_twist_keyboard.  The launch-level teleop node is
        # never needed from the web GUI.
        f"use_teleop:=false",
    ]
    # input= is only meaningful when the EEG node actually runs.
    if run_eeg and cfg.eeg.input:
        cmd.append(f"input:={cfg.eeg.input}")
    if run_eeg and cfg.eeg.role:
        cmd.append(f"role:={cfg.eeg.role}")
    if not use_sim:
        cmd.append(f"device:={launch.device}")
    return cmd


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _source_prefix() -> str:
    repo_setup = _repo_root() / "install" / "setup.bash"
    parts = ["source /opt/ros/kilted/setup.bash"]
    if repo_setup.exists():
        parts.append(f"source {shlex.quote(str(repo_setup))}")
    return " && ".join(parts)


def _load_ros_env() -> dict[str, str]:
    """Load ROS environment variables by sourcing setup scripts once."""
    global _ros_env_cache
    if _ros_env_cache is not None:
        return _ros_env_cache

    try:
        command = f"{_source_prefix()} && env -0"
        raw = subprocess.check_output(["bash", "-lc", command])
        env: dict[str, str] = {}
        for entry in raw.split(b"\0"):
            if not entry:
                continue
            key, sep, value = entry.partition(b"=")
            if not sep:
                continue
            env[key.decode("utf-8", errors="ignore")] = value.decode("utf-8", errors="ignore")
        _ros_env_cache = env or os.environ.copy()
    except Exception:
        _ros_env_cache = os.environ.copy()

    return _ros_env_cache


def _spawn_ros_command(command: list[str]) -> subprocess.Popen[str]:
    env = _load_ros_env()
    return subprocess.Popen(
        command,
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        shell=False,
    )


def _stop_runtime_processes() -> None:
    global _runtime_processes
    for process in _runtime_processes:
        if process.poll() is not None:
            continue
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2.0)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    _runtime_processes = []


def start_system(cfg: AppConfig, dry_run: bool = True) -> CommandResult:
    cmd = _build_launch_command(cfg)
    cmd_str = " ".join(cmd)  # For display only
    allow_real = os.getenv("WEB_GUI_ALLOW_REAL_COMMANDS", "true").lower() in {"1", "true", "yes"}

    if dry_run or not allow_real:
        set_runtime_state(True, None)
        return CommandResult(
            accepted=True,
            dry_run=True,
            command=cmd_str,
            detail="Dry-run mode. No command executed.",
        )

    _stop_runtime_processes()

    commands = [cmd]
    if cfg.launch.use_sim:
        commands.append(["ros2", "run", "thymio_web_bridge", "gazebo_camera_bridge"])

    for ros_command in commands:
        _runtime_processes.append(_spawn_ros_command(ros_command))

    set_runtime_state(True, None)
    use_sim = bool(cfg.launch.use_sim)
    run_eeg = bool(cfg.launch.run_eeg)
    if use_sim:
        detail = "Gazebo simulation started"
    else:
        detail = "Real Thymio system started"
    if run_eeg:
        detail += f" (input={cfg.eeg.input})"
    else:
        detail += " (manual teleop)"
    return CommandResult(
        accepted=True,
        dry_run=False,
        command=cmd_str,
        detail=detail + ".",
    )


_KILL_PATTERNS = [
    "ros2 launch thymio_control",
    "eeg_control_node",
    "gz sim",
    "gz server",
    "gz client",
    "parameter_bridge",
    "gazebo_camera_bridge",
    "robot_state_publisher",
    "asebaros",
    "thymio_driver",
]


def _kill_ros_processes() -> None:
    """Kill all known ROS/Gazebo processes by command pattern."""
    for pattern in _KILL_PATTERNS:
        try:
            subprocess.run(
                ["pkill", "-f", pattern],
                timeout=3,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass


def cleanup_residual_processes() -> str:
    """Kill any leftover ROS/Gazebo processes. Safe to call at startup."""
    import shutil
    if shutil.which("pkill") is None:
        return "pkill not available"
    _kill_ros_processes()
    return "Cleaned up residual processes"


def _send_stop_to_thymio() -> None:
    """Send zero velocity command to Thymio before stopping."""
    try:
        env = _load_ros_env()
        # Send zero velocity for 0.5 seconds
        subprocess.run(
            ["ros2", "topic", "pub", "--once", "/cmd_vel", "geometry_msgs/Twist",
             "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"],
            env=env,
            timeout=1.0,
            capture_output=True,
        )
    except Exception:
        pass  # Ignore errors (e.g., topic not available)


def stop_system(dry_run: bool = True) -> CommandResult:
    command = "; ".join(f"pkill -f '{p}'" for p in _KILL_PATTERNS)
    if dry_run:
        return CommandResult(
            accepted=True,
            dry_run=True,
            command=command,
            detail="(dry-run) Would terminate ROS/Gazebo processes.",
        )
    _send_stop_to_thymio()
    _stop_runtime_processes()
    _kill_ros_processes()
    set_runtime_state(False, None)
    return CommandResult(
        accepted=True,
        dry_run=False,
        command=command,
        detail="ROS/Gazebo processes terminated.",
    )
