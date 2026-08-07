"""Command builders + an injectable Executor.

Builders are **pure** — they only turn config values into command lists, so
they are unit-testable without any subprocess.  The :class:`Executor`
wraps ``subprocess`` and is the single seam where real execution happens;
tests swap in a fake via :meth:`Executor.set_run_one` /
:meth:`Executor.set_spawn`, so the whole service runs headlessly on macOS.
"""
from __future__ import annotations

import subprocess
from shlex import quote as shlex_quote
from typing import Callable, List, Optional


class CompletedCommand:
    """Result of a one-shot command (exit code + captured output)."""

    def __init__(self, exit_code: int, stdout: str = "", stderr: str = "") -> None:
        self.exit_code = exit_code
        self.stdout = stdout or ""
        self.stderr = stderr or ""

    def ok(self, codes: tuple[int, ...] = (0,)) -> bool:
        """Whether the exit code counts as success (some tools, e.g. xcopy,
        return 1 for "copied files", which is still success)."""
        return self.exit_code in codes


def _tokenize_windows(cmd: str) -> List[str]:
    """Split a Windows command line into argv tokens.

    Rules (mirroring CommandLineToArgvW, the semantics ``subprocess`` uses
    on Windows): whitespace separates tokens, double quotes group text that
    may contain spaces and are stripped, backslashes are **literal** (no
    escape processing — so ``C:\\Program Files\\...`` stays intact).  This
    lets a non-IT operator write ``"C:\\Program Files\\Python\\python.exe"
    gpype_lsl_bridge.py`` in config.json and have it split correctly.
    """
    tokens: List[str] = []
    cur: List[str] = []
    in_quotes = False
    for ch in cmd:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch.isspace() and not in_quotes:
            if cur:
                tokens.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        tokens.append("".join(cur))
    if in_quotes:
        raise ValueError(f"命令的引号不配对: {cmd!r}")
    return tokens


# --- Pure builders ------------------------------------------------------

def build_wsl_detect_cmd(distro: str) -> List[str]:
    """Probe WSL: run ``echo ok`` and check the exit code."""
    return ["wsl", "-d", distro, "-e", "bash", "-lc", "echo ok"]


def build_wsl_cd_cmd(distro: str, repo_path: str, inner: str) -> List[str]:
    """Run *inner* (a shell command string) from the repo dir inside WSL."""
    return ["wsl", "-d", distro, "-e", "bash", "-lc", f"cd {shlex_quote(repo_path)} && {inner}"]


def build_sync_cmd(tool: str, src: str, dst: str) -> List[str]:
    """Copy a directory tree from WSL's ``\\wsl$`` share to a Windows dir.

    ``src``/``dst`` are full paths (Windows or UNC).  ``tool`` is
    configurable because the operator's machine may prefer ``robocopy``.
    """
    if tool == "xcopy":
        return ["xcopy", "/E", "/I", "/Y", src, dst]
    if tool == "robocopy":
        return [
            "robocopy", src, dst, "/E", "/IS", "/IT",
            "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
        ]
    raise ValueError(f"未知同步工具: {tool!r} (支持 xcopy / robocopy)")


def build_start_web_cmds(config: dict) -> List[List[str]]:
    """One spawn per WSL-side service (backend, frontend), each a wsl bash."""
    distro = config["wsl"]["distro"]
    repo = config["wsl"]["repo_path"]
    return [
        build_wsl_cd_cmd(distro, repo, config["web"]["backend_cmd"]),
        build_wsl_cd_cmd(distro, repo, config["web"]["frontend_cmd"]),
    ]


def build_usbipd_attach_cmd(template: str) -> List[str]:
    return _tokenize_windows(template)


def build_usbipd_detach_cmd(template: str) -> List[str]:
    return _tokenize_windows(template)


def build_bridge_command(command: str) -> List[str]:
    """Tokenize a device command (e.g. ``python gpype_lsl_bridge.py``)."""
    return _tokenize_windows(command)


# --- Executor -----------------------------------------------------------

class Executor:
    """Runs one-shot commands and spawns long-running processes.

    All real IO is behind ``_run_one`` / ``_spawn_fn``; tests replace them.
    """

    def __init__(self) -> None:
        self._run_one: Callable[..., CompletedCommand] = self._default_run_one
        self._spawn_fn: Callable[..., subprocess.Popen] = self._default_spawn

    # -- injection seams ------------------------------------------------

    def set_run_one(self, fn: Callable[..., CompletedCommand]) -> None:
        """Replace one-shot execution (tests use this to fake wsl/xcopy)."""
        self._run_one = fn

    def set_spawn(self, fn: Callable[..., subprocess.Popen]) -> None:
        """Replace process spawn (tests fake long-running bridges/web)."""
        self._spawn_fn = fn

    # -- public API ------------------------------------------------------

    def run(
        self,
        cmd: List[str],
        *,
        timeout: int = 30,
        cwd: Optional[str] = None,
    ) -> CompletedCommand:
        return self._run_one(cmd, timeout=timeout, cwd=cwd)

    def spawn(self, cmd: List[str], *, cwd: Optional[str] = None) -> subprocess.Popen:
        return self._spawn_fn(cmd, cwd=cwd)

    # -- defaults (real execution) --------------------------------------

    def _default_run_one(self, cmd, timeout, cwd) -> CompletedCommand:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
        return CompletedCommand(proc.returncode, proc.stdout, proc.stderr)

    def _default_spawn(self, cmd, cwd) -> subprocess.Popen:
        # Long-running processes: discard output so the pipe can't fill and
        # deadlock; the operator watches the device/service state instead.
        return subprocess.Popen(
            cmd, cwd=cwd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
