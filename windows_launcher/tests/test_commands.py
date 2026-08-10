"""Command builders + Executor seams (no real subprocesses)."""
from commands import (
    CompletedCommand,
    Executor,
    build_bridge_command,
    build_start_web_cmds,
    build_sync_cmd,
    build_usbipd_attach_cmd,
    build_wsl_system_running_cmd,
)


def test_wsl_system_running_cmd_shape():
    assert build_wsl_system_running_cmd("Ubuntu") == [
        "wsl", "-d", "Ubuntu", "-e", "bash", "-lc", "systemctl is-system-running",
    ]


def test_sync_cmd_xcopy():
    cmd = build_sync_cmd("xcopy", r"\\wsl$\Ubuntu\home\robot\repo", r"C:\dst\repo")
    assert cmd[0] == "xcopy"
    assert cmd[-2:] == [r"\\wsl$\Ubuntu\home\robot\repo", r"C:\dst\repo"]


def test_sync_cmd_robocopy():
    cmd = build_sync_cmd("robocopy", "src", "dst")
    assert cmd[0] == "robocopy"


def test_sync_cmd_robocopy_excludes_config():
    """Finding C: config.json must be excluded from the launcher sync."""
    cmd = build_sync_cmd("robocopy", "src", "dst", exclude=["config.json"])
    assert "/XF" in cmd
    assert cmd[cmd.index("/XF") + 1] == "config.json"


def test_sync_cmd_xcopy_with_exclude_raises():
    """xcopy cannot exclude inline — raise rather than clobber local config."""
    import pytest

    with pytest.raises(ValueError, match="robocopy"):
        build_sync_cmd("xcopy", "src", "dst", exclude=["config.json"])


def test_sync_cmd_unknown_tool_raises():
    import pytest

    with pytest.raises(ValueError, match="未知同步工具"):
        build_sync_cmd("cp", "src", "dst")


def test_start_web_cmds_two_spawns_with_cd():
    cfg = {
        "wsl": {"distro": "Ubuntu", "repo_path": "/home/robot/TelekineRob-BCI"},
        "web": {"backend_cmd": "python -m app.main", "frontend_cmd": "npm run dev"},
    }
    cmds = build_start_web_cmds(cfg)
    assert len(cmds) == 2
    assert cmds[0][:4] == ["wsl", "-d", "Ubuntu", "-e"]
    # repo path is quoted inside the bash -c payload
    assert "TelekineRob-BCI" in cmds[0][-1]
    assert "python -m app.main" in cmds[0][-1]
    assert "npm run dev" in cmds[1][-1]


def test_usbipd_attach_keeps_backslash_paths():
    cmd = build_usbipd_attach_cmd("usbipd attach --wsl=Ubuntu --busid=1-1")
    assert cmd == ["usbipd", "attach", "--wsl=Ubuntu", "--busid=1-1"]


def test_bridge_command_tokenize_keeps_quoted_paths():
    cmd = build_bridge_command('"C:\\Program Files\\Python\\python.exe" gpype_lsl_bridge.py')
    assert cmd[0] == "C:\\Program Files\\Python\\python.exe"
    assert cmd[1] == "gpype_lsl_bridge.py"


def test_completed_command_ok_codes():
    assert CompletedCommand(0).ok()
    assert not CompletedCommand(2).ok()
    assert CompletedCommand(1).ok((0, 1))  # xcopy "no files copied" → still success


def test_executor_run_uses_injected_fn():
    ex = Executor()
    calls = []
    ex.set_run_one(lambda cmd, timeout, cwd: calls.append(cmd) or CompletedCommand(0))
    result = ex.run(["wsl", "-e", "echo"], timeout=5)
    assert result.exit_code == 0
    assert calls == [["wsl", "-e", "echo"]]


def test_executor_spawn_uses_injected_fn():
    ex = Executor()
    marker = object()
    ex.set_spawn(lambda cmd, cwd: marker)
    assert ex.spawn(["python", "bridge.py"]) is marker
