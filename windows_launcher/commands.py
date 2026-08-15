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
        raise ValueError(f"unbalanced quotes in command: {cmd!r}")
    return tokens


# --- Pure builders ------------------------------------------------------

def build_wsl_system_running_cmd(distro: str) -> List[str]:
    """Probe WSL systemd readiness: ``systemctl is-system-running``.

    Deeper than a bare ``echo ok`` (which only proves the binary spawned):
    returns ``running`` / ``degraded`` once Ubuntu has actually booted and
    the ``\\wsl$`` share + services the chain depends on are up (finding).
    """
    return ["wsl", "-d", distro, "-e", "bash", "-lc", "systemctl is-system-running"]


def build_wsl_cd_cmd(distro: str, repo_path: str, inner: str) -> List[str]:
    """Run *inner* (a shell command string) from the repo dir inside WSL."""
    return ["wsl", "-d", distro, "-e", "bash", "-lc", f"cd {shlex_quote(repo_path)} && {inner}"]


def build_wsl_hostname_cmd(distro: str) -> List[str]:
    """P39②: current WSL IP — ``hostname -I`` prints space-separated addrs;
    the FIRST segment is the WSL NAT IP (172.27.x), which changes on every
    WSL restart."""
    return ["wsl", "-d", distro, "-e", "bash", "-lc", "hostname -I"]


def build_portproxy_delete_cmd(listen_address: str, port: int = 5173) -> List[str]:
    """P39③: drop the OLD forwarding rule so the re-hang is idempotent
    (``delete`` on a missing rule errors — the caller ignores it)."""
    return [
        "netsh", "interface", "portproxy", "delete", "v4tov4",
        f"listenport={port}", f"listenaddress={listen_address}",
    ]


def build_portproxy_add_cmd(listen_address: str, port: int, connect_address: str) -> List[str]:
    """P39③: LAN → WSL forwarding for the FRONTEND port only (5173); the
    backend stays loopback (backend_url 8010 is not forwarded)."""
    return [
        "netsh", "interface", "portproxy", "add", "v4tov4",
        f"listenport={port}", f"listenaddress={listen_address}",
        f"connectport={port}", f"connectaddress={connect_address}",
    ]


def build_portproxy_show_cmd() -> List[str]:
    """P42①: READ the current portproxy rules — a read needs NO admin."""
    return ["netsh", "interface", "portproxy", "show", "all"]


def parse_portproxy_5173_connectaddress(show_output: str) -> Optional[str]:
    """P42①: the 5173 rule's connectaddress from ``netsh ... portproxy show``
    output. Matched NUMERICALLY (the listening-side port == 5173), never by
    header text — localized headers (Chinese / French / ...) differ but the
    numbers don't. Returns None when there is no 5173 rule."""
    for line in show_output.splitlines():
        fields = line.split()
        # data row: listenaddress  listenport  connectaddress  connectport
        if len(fields) >= 4 and fields[1].isdigit() and int(fields[1]) == 5173:
            return fields[2]
    return None


def build_uac_fix_cmd(ps1_path: str) -> List[str]:
    """P42③: raise the standard UAC prompt to run the fix script ELEVATED —
    ``Start-Process powershell -Verb runas -ArgumentList '-File', '<ps1>'``.
    Quoting stays clean because the .ps1 holds the netsh commands verbatim."""
    return [
        "powershell", "-NoProfile", "-Command",
        f"Start-Process powershell -Verb runas -ArgumentList '-File', '{ps1_path}'",
    ]


def build_sync_cmd(
    tool: str,
    src: str,
    dst: str,
    exclude: Optional[List[str]] = None,
) -> List[str]:
    """Copy a directory tree from WSL's ``\\wsl$`` share to a Windows dir.

    ``src``/``dst`` are full paths (Windows or UNC).  *exclude* lists file
    names to skip (e.g. the machine-local ``config.json`` must not be
    overwritten by the WSL repo's copy — finding C).

    ``tool`` defaults to ``robocopy`` because it supports inline file
    exclusion (``/XF``) and its exit codes 0–7 are all success; ``xcopy``
    cannot exclude inline, so requesting excludes with it raises rather
    than silently clobbering the local config.
    """
    exclude = list(exclude or [])
    if tool == "robocopy":
        cmd = [
            "robocopy", src, dst, "/E", "/IS", "/IT",
            "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
        ]
        if exclude:
            cmd += ["/XF", *exclude]
        return cmd
    if tool == "xcopy":
        if exclude:
            raise ValueError(
                "xcopy cannot exclude files — use robocopy for sync.tool in config.json"
            )
        return ["xcopy", "/E", "/I", "/Y", src, dst]
    raise ValueError(f"unknown sync tool: {tool!r} (supported: robocopy / xcopy)")


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


def build_python_script_cmd(python_cmd: str, script: str) -> List[str]:
    """Build ``[python_cmd, script]``.

    P8c: ``python_cmd`` is machine-local config (a venv python, possibly a
    path with spaces), so it is tokenized; the script is appended verbatim.
    Used for both the bridge commands and the LSL probe.
    """
    return _tokenize_windows(python_cmd) + [script]


def build_ide_open_cmd(open_cmd: str) -> List[str]:
    """Tokenize a configured open-in-IDE command (P8d, machine-local)."""
    return _tokenize_windows(open_cmd)


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

    def spawn(
        self,
        cmd: List[str],
        *,
        cwd: Optional[str] = None,
        log_file: Optional[str] = None,
    ) -> subprocess.Popen:
        return self._spawn_fn(cmd, cwd=cwd, log_file=log_file)

    # -- defaults (real execution) --------------------------------------

    def _default_run_one(self, cmd, timeout, cwd) -> CompletedCommand:
        # P4: the service runs under pythonw (no console), and on Windows a
        # console-less parent's children each open their own cmd window.
        # CREATE_NO_WINDOW suppresses that for probes/sync/usbipd/bridges;
        # POSIX has no such flag, so getattr(..., 0) degrades to the default.
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return CompletedCommand(proc.returncode, proc.stdout, proc.stderr)

    def _default_spawn(self, cmd, cwd, log_file=None) -> subprocess.Popen:
        # P8a: with a per-device log_file, the bridge's stdout/stderr go to
        # disk (appended) so a failure is diagnosable instead of vanishing
        # into DEVNULL. Otherwise output is discarded to avoid pipe
        # deadlock. Same CREATE_NO_WINDOW as run_one (P4).
        out = open(log_file, "a", encoding="utf-8", buffering=1) if log_file else subprocess.DEVNULL
        return subprocess.Popen(
            cmd, cwd=cwd, stdout=out, stderr=out,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
