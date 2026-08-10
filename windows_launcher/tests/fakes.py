"""Shared fakes for launcher tests — no real subprocesses ever run."""

import subprocess

from commands import CompletedCommand


class FakeProc:
    """Stand-in for subprocess.Popen (bridge / wsl web processes)."""

    def __init__(self, alive: bool = True) -> None:
        self._alive = alive

    def poll(self):
        return None if self._alive else 1

    def terminate(self) -> None:
        self._alive = False

    def kill(self) -> None:
        self._alive = False

    def wait(self, timeout: float = 2.0) -> int:
        return 0


class FakeExecutor:
    """Records every run/spawn and returns canned results by command shape."""

    def __init__(
        self,
        *,
        detect_ok: bool = True,
        systemd_state: str = "running",
        hang_probes: int = 0,
        sync_ok: bool = True,
        verify_ok: bool = True,
        bridge_alive: bool = True,
        usbipd_ok: bool = True,
    ) -> None:
        self.run_calls: list[list[str]] = []
        self.spawn_calls: list[list[str]] = []
        self.spawn_cwds: list = []
        self.procs: list[FakeProc] = []
        self.detect_ok = detect_ok
        self.systemd_state = systemd_state
        self.hang_probes = hang_probes
        self.sync_ok = sync_ok
        self.verify_ok = verify_ok
        self.bridge_alive = bridge_alive
        self.usbipd_ok = usbipd_ok

    def run(self, cmd, *, timeout, cwd=None) -> CompletedCommand:
        self.run_calls.append(cmd)
        head, tail = cmd[:1], cmd[-1]
        if head == ["wsl"] and "is-system-running" in tail:
            if self.hang_probes > 0:
                # O32: model a probe that hangs/times out.
                self.hang_probes -= 1
                raise subprocess.TimeoutExpired(cmd, timeout)
            if not self.detect_ok:
                return CompletedCommand(1, "starting", "")
            # O31: real systemd reports "degraded" with exit code 1 — the
            # fake models reality so the test doesn't mask the mismatch.
            if self.systemd_state == "degraded":
                return CompletedCommand(1, "degraded", "")
            return CompletedCommand(0, "running", "")
        if head in (["xcopy"], ["robocopy"]):
            # robocopy: 0–7 are success, >=8 are real failures
            return CompletedCommand(0 if self.sync_ok else 8)
        if head == ["wsl"] and "ttyACM0" in tail:
            return CompletedCommand(0 if self.verify_ok else 1, "ok" if self.verify_ok else "")
        if head == ["wsl"] and "pkill" in tail:
            return CompletedCommand(0)
        if head == ["usbipd"]:
            return CompletedCommand(0 if self.usbipd_ok else 1)
        return CompletedCommand(0)

    def spawn(self, cmd, *, cwd=None) -> FakeProc:
        self.spawn_calls.append(cmd)
        self.spawn_cwds.append(cwd)
        p = FakeProc(alive=self.bridge_alive)
        self.procs.append(p)
        return p
