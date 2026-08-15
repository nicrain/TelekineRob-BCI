"""O2 Windows launcher — control service (stdlib only, zero pip deps).

Serves the console page, exposes the §3 endpoints, and executes local
Windows commands (wsl / usbipd / xcopy / python) through an injectable
:class:`~commands.Executor`.  Everything except the real subprocess calls
is pure or fakeable, so the service is fully unit-testable on macOS.

Run (Windows, from this directory)::

    python launcher_server.py

Then open http://127.0.0.1:8020/ (or the port from config.json).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from commands import (
    Executor,
    build_bridge_command,
    build_ide_open_cmd,
    build_python_script_cmd,
    build_start_web_cmds,
    build_sync_cmd,
    build_usbipd_attach_cmd,
    build_usbipd_detach_cmd,
    build_wsl_cd_cmd,
    build_wsl_system_running_cmd,
)
from config import load_config
from state import (
    DEVICE_CONNECTED,
    DEVICE_CONNECTING,
    DEVICE_DISCONNECTED,
    DEVICE_DISCONNECTING,
    DEVICE_ERROR,
    SYSTEM_ERROR,
    SYSTEM_RUNNING,
    SYSTEM_STARTING,
    SYSTEM_STOPPED,
    SYSTEM_STOPPING,
    LauncherState,
    can_connect_device,
    can_start_system,
    can_stop_system,
    status_payload,
)

HERE = Path(__file__).resolve().parent
LSL_PROBE = HERE / "lsl_probe.py"
STATIC_DIR = HERE / "static"
DEFAULT_CONFIG = HERE / "config.json"
LOG_FILE = HERE / "launcher_server.log"
PID_FILE = HERE / "launcher_server.pid"

NOT_IMPLEMENTED = "Not implemented yet"


def _setup_logging() -> None:
    """Route stdout/stderr to ``launcher_server.log`` and echo to the console.

    Under ``pythonw`` (windowless, P1) there is no console — ``sys.stdout``
    is None — so without this every ``print()`` in the service would raise
    and the logs would vanish with the window. The tee writes the log file
    always and mirrors to the console when one exists, so the existing
    ``print()`` calls stay untouched.
    """
    console = sys.stdout
    file_handle = open(LOG_FILE, "a", encoding="utf-8", buffering=1)

    class _Tee:
        def write(self, data: str) -> int:
            file_handle.write(data)
            if console is not None:
                try:
                    console.write(data)
                except Exception:
                    pass
            return len(data)

        def flush(self) -> None:
            file_handle.flush()
            if console is not None:
                try:
                    console.flush()
                except Exception:
                    pass

    sys.stdout = sys.stderr = _Tee()


def write_pidfile() -> None:
    """Record this service's PID so launcher.bat can replace it (P1)."""
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def remove_pidfile() -> None:
    """Best-effort pidfile cleanup (never raises)."""
    try:
        PID_FILE.unlink()
    except OSError:
        pass


# --- Human-readable errors ---------------------------------------------

def friendly_error(exc: Exception, action: str = "") -> str:
    """Map an exception to one English sentence — no stack trace (§4)."""
    prefix = f"{action}: " if action else ""
    if isinstance(exc, FileNotFoundError):
        return prefix + "command not found — check it is installed and on PATH"
    if isinstance(exc, subprocess.TimeoutExpired):
        return prefix + "operation timed out — check WSL / device readiness"
    if isinstance(exc, (urllib.error.URLError, ConnectionError, TimeoutError)):
        return prefix + "web service unreachable — try again later"
    if isinstance(exc, (ValueError, RuntimeError)):
        # Our own raised errors already carry an English, operator-facing
        # sentence — surface it verbatim (no stack).
        return prefix + str(exc)
    return prefix + f"an error occurred ({type(exc).__name__})"


# --- App ------------------------------------------------------------------

class LauncherApp:
    """Holds config + state + executor; each method is one sidebar action."""

    def __init__(
        self,
        config: dict,
        executor: Optional[Executor] = None,
        ready_check: Optional[Callable[[str, float], bool]] = None,
    ) -> None:
        self.config = config
        self.executor = executor or Executor()
        self.state = LauncherState(list(config.get("devices", {}).keys()))
        # Poll the web GUI until it answers (injectable for tests).
        self._ready_check = ready_check or self._default_ready_check
        self._lock = threading.RLock()
        self._web_procs: List[subprocess.Popen] = []
        self._device_procs: Dict[str, subprocess.Popen] = {}
        # IDE-mode devices run no launcher process — LSL presence is their
        # truth. The reconcile probe is throttled (avoid a subprocess every
        # 1.5 s poll) via this per-device last-check timestamp (P8d).
        self._last_lsl_check: Dict[str, float] = {}
        # P10②/P10①: same throttling for the usbipd ttyACM0 probe and the
        # web-service health probe — status() runs every 1.5 s and neither
        # should spawn a probe (WSL subprocess / HTTP) every single time.
        self._last_verify_check: Dict[str, float] = {}
        self._last_system_health_check = 0.0
        self._system_health_interval = float(config["web"].get("health_interval_sec", 10))
        # P11-fix②: devices greyed out by a STALLED stream (not an explicit
        # disconnect) are marked so reconcile can auto-green them when the
        # bridge self-recovers (unicornpy O4 / gpype P10 watchdog). Explicit
        # disconnect/connect clears the mark → no surprise auto-recover.
        self._stalled: Dict[str, bool] = {}
        # P15②: per-device connect generation — the background LSL wait
        # (open_in_ide) captures its own instance's generation and discards a
        # late result when a disconnect→reconnect superseded it.
        self._connect_gen: Dict[str, int] = {}

        # Origin whitelist for the action POSTs (finding A). The console
        # page is same-origin, so its browser requests always carry one of
        # the service's own origins (127.0.0.1 or localhost on the bound
        # port); config may add more (e.g. a LAN address if host≠loopback).
        host = config["service"].get("host", "127.0.0.1")
        port = int(config["service"].get("port", 8020))
        self._allowed_origins = set(config["service"].get("allowed_origins", [])) | {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }

    def validate_origin(self, origin: str) -> bool:
        """Reject POSTs from pages not served by this console (finding A).

        Mirrors web_gui's ``_validate_origin``: http/https scheme + member
        of the whitelist. Browsers always send ``Origin`` on POSTs, so an
        arbitrary webpage can no longer fire /start-system etc. at the
        loopback service (CSRF-style); curl/scripts without an Origin are
        also rejected (defence-in-depth).
        """
        if not origin or not isinstance(origin, str):
            return False
        if not (origin.startswith("http://") or origin.startswith("https://")):
            return False
        return origin in self._allowed_origins

    def register_port(self, port: int) -> None:
        """Adopt the port the server actually bound.

        Production binds the config port, so this is a no-op; tests bind an
        ephemeral port and must still pass their own origin.
        """
        self._allowed_origins.update(
            {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        )

    # -- read endpoints --------------------------------------------------

    def status(self) -> dict:
        # Reconcile before reporting so a bridge that died without an
        # explicit disconnect shows red/grey, not a stale "connected" (§4:
        # 状态显示反映真实系统).
        self._reconcile_proc_health()
        self._reconcile_system_health()
        return status_payload(self.state)

    def _reconcile_proc_health(self) -> None:
        now = time.time()
        for name, dev in self.config["devices"].items():
            # P10②: usbipd attach survives launcher restarts — reconcile the
            # Thymio state to the REAL attach status (ttyACM0 in WSL).
            if dev.get("type") == "usbipd":
                self._reconcile_usbipd(name, dev)
                continue
            if dev.get("type") != "bridge":
                continue
            # Bridge devices (P11): green means the stream has DATA, not
            # that a process is alive. Design: a stalled device is left GREY
            # with the bridge alive so it can self-recover (unicornpy O4 /
            # gpype P10 watchdog) — never killed here; a DEAD process is RED.
            if dev.get("connect_mode") != "open_in_ide":
                proc = self._device_procs.get(name)
                if proc is not None and proc.poll() is not None and self.state.devices[name] in (
                    DEVICE_CONNECTED, DEVICE_CONNECTING,
                ):
                    self.state.set_device(name, DEVICE_ERROR, "bridge process exited")
                    self._stalled.pop(name, None)
                    continue
            if self.state.devices[name] == DEVICE_CONNECTED:
                if now - self._last_lsl_check.get(name, 0.0) < 10.0:
                    continue
                self._last_lsl_check[name] = now
                if self._lsl_state(dev) != "alive":
                    # downgrade: stream empty/gone (device off) → grey.
                    self._stalled[name] = True
                    self.state.set_device(name, DEVICE_DISCONNECTED, "")
            elif self.state.devices[name] == DEVICE_DISCONNECTED and self._stalled.get(name):
                # P11-fix②: the device came back and the bridge self-
                # recovered → auto-green, no manual reconnect. Only devices
                # greyed out BY STALL (not explicitly disconnected) qualify.
                if now - self._last_lsl_check.get(name, 0.0) < 10.0:
                    continue
                self._last_lsl_check[name] = now
                if self._lsl_state(dev) == "alive":
                    self._stalled[name] = False
                    self.state.set_device(name, DEVICE_CONNECTED, "Connected")

    def _reconcile_usbipd(self, name: str, dev: dict) -> None:
        """P10②: align Thymio state with the real attach status.

        ``usbipd attach`` persists across launcher restarts, so a fresh
        launcher must show an already-attached device as connected instead
        of waiting for a connect click — and a device detached outside the
        launcher must fall back to grey. Throttled so status() (1.5 s poll)
        doesn't spawn a WSL subprocess every time.
        """
        if self.state.system not in (SYSTEM_RUNNING, SYSTEM_STARTING):
            return  # WSL is down — probing ttyACM0 would boot it pointlessly
        now = time.time()
        if now - self._last_verify_check.get(name, 0.0) < float(dev.get("reconcile_sec", 10)):
            return
        self._last_verify_check[name] = now
        if self._thymio_attached(dev):
            if self.state.devices[name] == DEVICE_DISCONNECTED:
                self.state.set_device(name, DEVICE_CONNECTED, "Connected")
        elif self.state.devices[name] == DEVICE_CONNECTED:
            self.state.set_device(name, DEVICE_DISCONNECTED, "")

    def _reconcile_system_health(self) -> None:
        """P10①/P14: while 'running', the web system is the truth — BOTH the
        frontend (5173) and the backend (8010 /api/status) must answer.
        Probing only the frontend is not enough: vite is independent of the
        backend, so a dead backend still reports healthy (P14). Either down
        → error + the Restart Web hint. Throttled."""
        if self.state.system != SYSTEM_RUNNING:
            return
        now = time.time()
        if now - self._last_system_health_check < self._system_health_interval:
            return
        self._last_system_health_check = now
        web = self.config["web"]
        backend = (
            web.get("backend_url", "http://localhost:8010").rstrip("/")
            + "/api/status"
        )
        if not (self._ready_check(web["url"], 2.0)
                and self._ready_check(backend, 2.0)):
            self.state.set_system(
                SYSTEM_ERROR, "web service unreachable — restart the web services"
            )

    def sidebar_config(self) -> dict:
        """Safe subset for ``GET /config`` (no command bodies)."""
        sidebar = self.config.get("sidebar", {})
        return {
            "groups": sidebar.get("groups", []),
            "log": sidebar.get("log"),
            "web_url": self.config.get("web", {}).get("url", "http://localhost:5173"),
        }

    def log_tail(self, lines: int = 200) -> List[dict]:
        """P17②: tail the launcher's own log + per-device bridge logs for the
        View Log button (launcher_server.log + bridge_<device>.log in HERE)."""
        out: List[dict] = []
        for path in sorted(HERE.glob("*.log")):
            try:
                tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
            except OSError:
                continue
            out.append({"source": path.name, "lines": tail})
        return out

    # -- process management primitives -----------------------------------

    def _terminate_proc(self, proc: subprocess.Popen, wait_sec: float = 2.0) -> None:
        """Terminate a spawned process; escalate to kill if it lingers."""
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=wait_sec)
        except subprocess.TimeoutExpired:
            proc.kill()

    # -- M3: system chain ------------------------------------------------

    def start_system(self) -> dict:
        """wsl 检测 → 同步 launcher+桥文件（自同步）→ 起前后端 → 就绪检测."""
        with self._lock:
            if not can_start_system(self.state):
                return {"ok": True, "message": "System already starting or running"}
            self.state.set_system(SYSTEM_STARTING, "Starting…")
        try:
            self._detect_wsl()
            self._sync_files()
            # P38①/③: pre-clean before spawning — a retry must not leak a
            # zombie vite/app.main, and 5173/8010 are free to re-bind.
            self._clear_web_procs()
            self._run_web_stop_cmd()
            self._spawn_web_services()
            if not self._wait_ready(
                self.config["web"]["url"],
                float(self.config["web"].get("ready_timeout_sec", 60)),
            ):
                raise RuntimeError("web service not ready (timeout) — check the frontend")
            self.state.set_system(SYSTEM_RUNNING, "System ready")
            return {"ok": True, "message": "System started and ready"}
        except Exception as exc:
            self._clear_web_procs()   # P38③: no leak on failure
            self.state.set_system(SYSTEM_ERROR, friendly_error(exc, "Start System"))
            return {"ok": False, "message": self.state.system_msg}

    def _detect_wsl(self) -> None:
        """Poll until Ubuntu is actually ready, not just spawned.

        ``echo ok`` only proves the binary ran — the ``\\wsl$`` share and
        systemd may still be booting, and every later step (sync, web
        spawn) would fail. Accept ``systemctl is-system-running`` =
        running/degraded, or the ``\\wsl$`` share being reachable (covers
        WSL setups without systemd). Timeout → one-line Chinese error.
        """
        cfg = self.config["wsl"]
        timeout = float(cfg.get("ready_timeout_sec", 60))
        interval = float(cfg.get("ready_poll_sec", 2))
        deadline = time.time() + timeout
        cmd = build_wsl_system_running_cmd(cfg["distro"])
        while time.time() < deadline:
            # O31: the OUTPUT is authoritative — real systemd reports
            # "degraded" with exit code 1, so gating on result.ok() (0 only)
            # would never accept it. O32: a single probe timing out must not
            # abort the whole poll — keep polling until the total deadline.
            try:
                result = self.executor.run(cmd, timeout=10)
                state = (result.stdout + result.stderr).strip()
                if state in ("running", "degraded"):
                    return
            except Exception:
                pass
            if self._share_accessible():
                return
            time.sleep(interval)
        raise RuntimeError(
            f"WSL ({cfg['distro']}) not ready: systemd/share not up within "
            f"{timeout:.0f}s — check WSL"
        )

    def _share_accessible(self) -> bool:
        """Windows-side probe of the ``\\wsl$`` repo share."""
        return os.path.exists(self.config["sync"]["src_wsl_root"])

    def _sync_files(self) -> None:
        """Copy launcher + bridge files from WSL → Windows (§1.1 self-sync).

        Machine-local ``config.json`` is excluded (finding C): the operator
        fills it once on Windows and must not have it reverted to the WSL
        repo's placeholder on every start-system.
        """
        sync = self.config["sync"]
        for item in sync["items"]:
            rel = item["src"]
            src = sync["src_wsl_root"] + "\\" + rel
            dst = sync["dst_root"] + "\\" + rel
            result = self.executor.run(
                build_sync_cmd(sync["tool"], src, dst, item.get("exclude")),
                timeout=60,
            )
            codes = tuple(sync.get("success_exit_codes", [0]))
            if not result.ok(codes):
                raise RuntimeError(f"sync of {rel} failed (exit {result.exit_code})")

    def _run_web_stop_cmd(self) -> None:
        """P38①: pkill any leftover web processes in WSL (app.main + vite) so
        a (re)start begins with 5173/8010 free — idempotent retries."""
        stop_cmd = self.config["web"].get("stop_cmd")
        if not stop_cmd:
            return
        self.executor.run(
            build_wsl_cd_cmd(
                self.config["wsl"]["distro"],
                self.config["wsl"]["repo_path"],
                stop_cmd,
            ),
            timeout=30,
        )

    def _clear_web_procs(self) -> None:
        """P38③: terminate + drop the tracked web processes — called before a
        (re)spawn and on the failure path so no zombie vite leaks."""
        for proc in self._web_procs:
            self._terminate_proc(proc)
        self._web_procs.clear()

    def _spawn_web_services(self) -> None:
        for cmd in build_start_web_cmds(self.config):
            self._web_procs.append(self.executor.spawn(cmd))

    def _wait_ready(self, url: str, timeout: float) -> bool:
        return self._ready_check(url, timeout)

    def stop_system(self) -> dict:
        """停桥进程 + 停 web 进程 + 停 WSL（§1.3 关闭流程）。"""
        with self._lock:
            if not can_stop_system(self.state):
                return {"ok": True, "message": "System stopped"}
            self.state.set_system(SYSTEM_STOPPING, "Stopping…")
        try:
            for proc in self._device_procs.values():
                self._terminate_proc(proc)
            self._device_procs.clear()
            self._clear_web_procs()
            if self.config["wsl"].get("stop_wsl", True):
                try:
                    self.executor.run(
                        ["wsl", "--terminate", self.config["wsl"]["distro"]],
                        timeout=30,
                    )
                except Exception:
                    pass  # best-effort: WSL may already be down
            self.state.set_system(SYSTEM_STOPPED, "System stopped")
            for name in self.state.devices:
                self.state.set_device(name, DEVICE_DISCONNECTED, "")
            # P15①: the IDE bridge (headband) runs in VS Code and is NOT killed
            # by stop — a leftover _stalled mark would let reconcile auto-green
            # the device once its stream comes back, while the system is
            # stopped. Clear every device's mark at the stop boundary (also
            # keeps the next start from surprise-auto-green on a stale flag).
            self._stalled.clear()
            return {"ok": True, "message": "System stopped"}
        except Exception as exc:
            self.state.set_system(SYSTEM_ERROR, friendly_error(exc, "Stop System"))
            return {"ok": False, "message": self.state.system_msg}

    def restart_web(self) -> dict:
        """停掉旧 web 进程（pkill）并重新拉起。"""
        with self._lock:
            if not can_stop_system(self.state):
                return {"ok": False, "message": "System not running — nothing to restart"}
            self.state.set_system(SYSTEM_STARTING, "Restarting web services…")
        try:
            # P38①/③: pre-clean (pkill leftovers) then drop old handles before
            # respawning; on failure the NEW spawns are cleaned too.
            self._run_web_stop_cmd()
            self._clear_web_procs()
            self._spawn_web_services()
            if not self._wait_ready(
                self.config["web"]["url"],
                float(self.config["web"].get("ready_timeout_sec", 60)),
            ):
                raise RuntimeError("web service not ready (timeout) — check the frontend")
            self.state.set_system(SYSTEM_RUNNING, "System ready")
            return {"ok": True, "message": "Web services restarted"}
        except Exception as exc:
            self._clear_web_procs()   # P38③: no leak on failure
            self.state.set_system(SYSTEM_ERROR, friendly_error(exc, "Restart Web"))
            return {"ok": False, "message": self.state.system_msg}

    def restart_system(self) -> dict:
        """③ P10: full stop-then-start (the running-state Start button).

        The frontend shows "Restart System" while running and POSTs
        /restart-system; the server owns the stop→start ordering."""
        with self._lock:
            if not can_stop_system(self.state):
                return {"ok": False, "message": "System not running — nothing to restart"}
        stopped = self.stop_system()
        if not stopped["ok"]:
            return stopped
        return self.start_system()

    # -- M4: device chain -------------------------------------------------

    def connect_device(self, name: str) -> dict:
        with self._lock:
            if name not in self.config["devices"]:
                return {"ok": False, "message": f"Unknown device: {name}"}
            if not can_connect_device(self.state):
                return {"ok": False, "message": "System not ready — start the system first"}
            dev = self.config["devices"][name]
            if self.state.devices[name] in (DEVICE_CONNECTING, DEVICE_CONNECTED):
                return {"ok": True, "message": f"{dev['label']} connected"}
            self.state.set_device(name, DEVICE_CONNECTING, "Connecting…")
            # P11-fix②: a connect intent is explicit — clear any stall mark
            # so the stale-grey auto-recover flag doesn't outlive it.
            self._stalled.pop(name, None)
            # P15②: each connect intent is a NEW generation — the background
            # LSL wait captures it and drops a result from an instance a newer
            # disconnect→reconnect superseded.
            self._connect_gen[name] = self._connect_gen.get(name, 0) + 1
        try:
            if dev.get("connect_mode") == "open_in_ide":
                # P8d: returns immediately with the "press Run" prompt; the
                # LSL wait runs in a background thread.
                return self._connect_open_in_ide(name, dev)
            dev_type = dev["type"]
            if dev_type == "bridge":
                self._connect_bridge(name, dev)
            elif dev_type == "usbipd":
                self._connect_usbipd(name, dev)
            else:
                raise ValueError(f"Unknown device type: {dev_type!r}")
            self.state.set_device(name, DEVICE_CONNECTED, "Connected")
            return {"ok": True, "message": f"{dev['label']} connected"}
        except Exception as exc:
            self.state.set_device(
                name, DEVICE_ERROR, friendly_error(exc, f"Connect {dev['label']}")
            )
            return {"ok": False, "message": self.state.device_msgs[name]}

    def _connect_bridge(self, name: str, dev: dict) -> None:
        """Spawn the LSL bridge and verify by stream, not by process (P8b):
        green means the LSL stream is actually up. Timeout → terminate the
        bridge and fail with a human message."""
        # P11-fix①: a stale bridge from a stalled grey-out is kept alive by
        # reconcile (so it can self-recover) — terminate it BEFORE spawning
        # the new one, symmetric with disconnect. Otherwise the old process
        # leaks, holds the device ("device in use") and publishes a second
        # outlet with the same source_id, making the probe non-deterministic.
        self._terminate_proc(self._device_procs.pop(name, None))
        cmd = build_python_script_cmd(dev.get("python_cmd", "python"), dev["script"])
        log_path = self._bridge_log_path(name)
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(
                    f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"connect {name}: {' '.join(cmd)}\n"
                )
        except OSError:
            pass  # best-effort: the spawn still redirects to the log
        proc = self.executor.spawn(cmd, cwd=dev.get("cwd"), log_file=str(log_path))
        self._device_procs[name] = proc
        if not self._wait_for_lsl(dev):
            self._terminate_proc(proc)
            raise RuntimeError("no LSL stream — check device is on")

    def _connect_open_in_ide(self, name: str, dev: dict) -> dict:
        """P8d: open the bridge script in the operator's IDE and wait for
        the LSL stream in the background (they press Run themselves)."""
        self._open_script(dev)
        self.state.set_device(name, DEVICE_CONNECTING, "waiting for LSL stream")
        # P13①: the operator runs the bridge in VS Code by hand — give them a
        # generous window (120s default) so a slow start doesn't flash red.
        timeout = float(dev.get("open_ide_timeout_sec", 120))
        poll = float(dev.get("verify_poll_sec", 2))
        # P15②: capture THIS connect instance's generation so the wait discards
        # its result if a newer connect superseded it before the probe lands.
        gen = self._connect_gen.get(name, 0)
        threading.Thread(
            target=self._wait_lsl_background,
            args=(name, dev, timeout, poll, gen),
            daemon=True,
        ).start()
        return {"ok": True, "message": "Bridge script opened in VS Code — press Run (F5) there to start it"}

    def _open_script(self, dev: dict) -> None:
        """Run the configured open-in-IDE command; fall back to the default
        opener (start) when `code` isn't on PATH (P8d)."""
        open_cmd = dev.get("open_cmd")
        if not open_cmd:
            raise RuntimeError("connect_mode 'open_in_ide' needs an open_cmd")
        try:
            self.executor.run(build_ide_open_cmd(open_cmd), timeout=10)
        except FileNotFoundError:
            fallback = dev.get("open_fallback_cmd")
            if not fallback:
                raise
            self.executor.run(build_ide_open_cmd(fallback), timeout=10)

    def _wait_lsl_background(
        self, name: str, dev: dict, timeout: float, poll: float, gen: int | None = None
    ) -> None:
        # P15②: default to the CURRENT generation so direct calls (tests)
        # belong to the live connect instance; the spawn passes its own.
        gen = self._connect_gen.get(name, 0) if gen is None else gen
        ok = self._wait_for_lsl(dev, timeout, poll)
        # P13①: the operator may have disconnected (or reconnected) while we
        # waited in the background — never override an explicit disconnect
        # with a late result.
        with self._lock:
            # P15②: a disconnect→reconnect bumped the generation — a result
            # from a superseded connect instance must not overwrite the new
            # instance's still-running wait.
            if self._connect_gen.get(name, 0) != gen:
                return
            if self.state.devices[name] != DEVICE_CONNECTING:
                return
            if ok:
                self.state.set_device(name, DEVICE_CONNECTED, "Connected")
            else:
                self.state.set_device(
                    name, DEVICE_ERROR,
                    "no LSL stream — confirm the bridge is running in VS Code",
                )

    # -- LSL stream verification (P8b) -----------------------------------

    def _bridge_log_path(self, name: str) -> Path:
        return HERE / f"bridge_{name}.log"

    def _wait_for_lsl(self, dev: dict, timeout: float | None = None, poll: float | None = None) -> bool:
        """Poll the LSL probe until the stream is ALIVE (has data) or timeout."""
        timeout = float(dev.get("verify_timeout_sec", 20)) if timeout is None else timeout
        poll = float(dev.get("verify_poll_sec", 2)) if poll is None else poll
        deadline = time.time() + timeout
        while True:
            if self._lsl_state(dev) == "alive":
                return True
            if time.time() >= deadline:
                return False
            time.sleep(poll)

    def _lsl_state(self, dev: dict) -> str:
        """Three-state LSL liveness probe (P11), run under the DEVICE's
        python_cmd (venv has pylsl); the launcher itself stays zero-dep.

        ``alive`` = the stream resolved AND yielded a sample (the device is
        actually streaming). ``stalled`` = resolved but empty — the bridge is
        still publishing while the device is off (the false-green case).
        ``not-found`` = no stream at all (bridge down)."""
        cmd = (
            build_python_script_cmd(dev.get("python_cmd", "python"), str(LSL_PROBE))
            + [dev.get("lsl_source_id", ""), "1"]
        )
        try:
            result = self.executor.run(cmd, timeout=10)
            lines = (result.stdout or "").splitlines()
        except Exception:
            return "not-found"
        # Line-exact match: the probe prints one full word per run; a
        # substring check would misfire (e.g. "not-found" ends with "found").
        if "alive" in lines:
            return "alive"
        if "stalled" in lines:
            return "stalled"
        return "not-found"

    def _thymio_attached(self, dev: dict) -> bool:
        """Whether the Thymio is already visible in WSL (ttyACM0)."""
        verify = dev.get("verify_cmd")
        if not verify:
            return False
        try:
            return self.executor.run(build_bridge_command(verify), timeout=30).ok()
        except Exception:
            return False

    def _connect_usbipd(self, name: str, dev: dict) -> None:
        """Attach the Thymio USB device via usbipd, then verify inside WSL.

        Idempotent (P10②): ``usbipd attach`` survives launcher restarts, so
        if the device is already attached (ttyACM0 visible in WSL) skip the
        attach instead of failing on "already attached".
        """
        if self._thymio_attached(dev):
            return
        result = self.executor.run(
            build_usbipd_attach_cmd(dev["attach_cmd"]), timeout=30,
        )
        if not result.ok():
            raise RuntimeError(
                f"usbipd attach failed (exit {result.exit_code})"
                f"{': ' + result.stderr.strip() if result.stderr.strip() else ''}"
            )
        time.sleep(float(dev.get("verify_delay_sec", 3)))
        verify = dev.get("verify_cmd")
        if verify:
            vresult = self.executor.run(build_bridge_command(verify), timeout=30)
            if not vresult.ok():
                raise RuntimeError("device verification failed (ttyACM0 not visible)")

    def disconnect_device(self, name: str) -> dict:
        with self._lock:
            if name not in self.config["devices"]:
                return {"ok": False, "message": f"Unknown device: {name}"}
            dev = self.config["devices"][name]
            if self.state.devices[name] == DEVICE_DISCONNECTED:
                # Already grey — including a stall-greyed device: an explicit
                # disconnect here cancels any pending auto-recover (P11-fix②)
                # and terminates the lingering self-recovering bridge (an
                # explicit disconnect means "no resources held").
                self._stalled.pop(name, None)
                self._terminate_proc(self._device_procs.pop(name, None))
                return {"ok": True, "message": f"{dev['label']} disconnected"}
            self.state.set_device(name, DEVICE_DISCONNECTING, "Disconnecting…")
        try:
            if dev.get("connect_mode") == "open_in_ide":
                # P8d: we cannot terminate a bridge running in VS Code —
                # reset the state and tell the operator to stop it there.
                self.state.set_device(name, DEVICE_DISCONNECTED, "")
                self._stalled.pop(name, None)  # explicit disconnect, no auto-recover
                return {"ok": True, "message": "Stop the bridge in VS Code"}
            dev_type = dev["type"]
            if dev_type == "bridge":
                self._terminate_proc(self._device_procs.pop(name, None))
            elif dev_type == "usbipd":
                result = self.executor.run(
                    build_usbipd_detach_cmd(dev["detach_cmd"]), timeout=30,
                )
                if not result.ok():
                    raise RuntimeError(
                        f"usbipd detach failed (exit {result.exit_code})"
                    )
            else:
                raise ValueError(f"Unknown device type: {dev_type!r}")
            self.state.set_device(name, DEVICE_DISCONNECTED, "")
            self._stalled.pop(name, None)  # explicit disconnect, no auto-recover
            return {"ok": True, "message": f"{dev['label']} disconnected"}
        except Exception as exc:
            self.state.set_device(
                name, DEVICE_ERROR, friendly_error(exc, f"Disconnect {dev['label']}")
            )
            return {"ok": False, "message": self.state.device_msgs[name]}

    # -- default ready check ----------------------------------------------

    @staticmethod
    def _default_ready_check(url: str, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    if resp.status == 200:
                        return True
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(1.0)
        return False


# --- HTTP layer ----------------------------------------------------------

class LauncherServer(ThreadingHTTPServer):
    """Threading server that carries the app instance for handlers."""

    daemon_threads = True

    def __init__(self, addr, app: LauncherApp) -> None:
        super().__init__(addr, Handler)
        self.app = app
        app.register_port(self.server_address[1])


class Handler(BaseHTTPRequestHandler):
    server_version = "LauncherO2/0.1"

    # -- helpers ----------------------------------------------------------

    def _send_json(self, obj: dict, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, code: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            return {}

    def log_message(self, fmt, *args) -> None:  # quieter console logs
        print("[launcher]", fmt % args, flush=True)

    # -- routes -----------------------------------------------------------

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            try:
                html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
            except FileNotFoundError:
                html = "<html><body><h1>Control page not ready</h1></body></html>"
            return self._send_html(html)
        if path == "/status":
            return self._send_json(self.server.app.status())
        if path == "/config":
            return self._send_json(self.server.app.sidebar_config())
        if path == "/log":
            # P17②: View Log — tail launcher_server.log + bridge_*.log.
            try:
                lines = int(urlparse(self.path).query.split("=")[1]) if "lines=" in urlparse(self.path).query else 200
            except (ValueError, IndexError):
                lines = 200
            return self._send_json({"ok": True, "logs": self.server.app.log_tail(lines)})
        return self._send_json({"ok": False, "message": "Unknown path"}, code=404)

    def do_POST(self):
        app = self.server.app
        # Finding A: /start-system /stop-system /restart-web and the device
        # POSTs are triggerable as CORS simple requests — any webpage could
        # fire them at the loopback service. Reject cross-origin POSTs.
        if not app.validate_origin(self.headers.get("Origin", "")):
            return self._send_json(
                {"ok": False, "message": "Cross-origin request rejected"}, code=403
            )
        path = urlparse(self.path).path
        try:
            if path == "/start-system":
                result = app.start_system()
            elif path == "/restart-system":
                result = app.restart_system()
            elif path == "/stop-system":
                result = app.stop_system()
            elif path == "/restart-web":
                result = app.restart_web()
            elif path == "/connect-device":
                result = app.connect_device(self._read_json().get("device", ""))
            elif path == "/disconnect-device":
                result = app.disconnect_device(self._read_json().get("device", ""))
            elif path == "/shutdown":
                # P1: windowless service needs an explicit stop. Delete the
                # pidfile, reply 200, then stop serve_forever from a worker
                # thread — calling server.shutdown() here would deadlock and
                # drop the response.
                remove_pidfile()
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return self._send_json({"ok": True, "message": "Launcher service exited"})
            else:
                return self._send_json({"ok": False, "message": "Unknown endpoint"}, code=404)
        except NotImplementedError as exc:
            result = {"ok": False, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 — operator-facing guard
            result = {"ok": False, "message": friendly_error(exc)}
        return self._send_json(result)


def main(argv: Optional[List[str]] = None) -> int:
    # argv is the arg list WITHOUT the script name (callers pass sys.argv[1:]).
    config_path = Path(argv[0]) if argv else DEFAULT_CONFIG
    _setup_logging()  # P1: tee to launcher_server.log even under pythonw
    try:
        config = load_config(config_path)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    host = config["service"].get("host", "127.0.0.1")
    port = int(config["service"].get("port", 8020))
    app = LauncherApp(config)
    try:
        server = LauncherServer((host, port), app)
    except OSError as exc:
        print(f"[ERROR] cannot start service (port {port} may be in use): {exc}")
        return 1
    print(f"[INFO] Launcher service started: http://{host}:{port}/")
    # Write the actual URL for launcher.bat to read — the bat never has to
    # parse config.json (avoids batch quoting pain) and stays correct even
    # if the operator changes the port.
    (HERE / "last_url.txt").write_text(f"http://{host}:{port}/\n", encoding="utf-8")
    write_pidfile()  # P1: bat 用它在下次双击时幂等替换
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        remove_pidfile()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
