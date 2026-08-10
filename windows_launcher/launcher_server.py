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
STATIC_DIR = HERE / "static"
DEFAULT_CONFIG = HERE / "config.json"
LOG_FILE = HERE / "launcher_server.log"
PID_FILE = HERE / "launcher_server.pid"

NOT_IMPLEMENTED = "该功能尚未开通"


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
    """Map an exception to one Chinese sentence — no stack trace (§4)."""
    prefix = f"{action}：" if action else ""
    if isinstance(exc, FileNotFoundError):
        return prefix + "找不到要执行的程序，请确认已安装并加入 PATH"
    if isinstance(exc, subprocess.TimeoutExpired):
        return prefix + "操作超时，请检查 WSL 或设备是否就绪"
    if isinstance(exc, (urllib.error.URLError, ConnectionError, TimeoutError)):
        return prefix + "网页服务连不上，请稍后再试"
    if isinstance(exc, (ValueError, RuntimeError)):
        # Our own raised errors already carry a Chinese, operator-facing
        # sentence — surface it verbatim (no stack).
        return prefix + str(exc)
    return prefix + f"发生错误（{type(exc).__name__}）"


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
        return status_payload(self.state)

    def _reconcile_proc_health(self) -> None:
        for name, proc in list(self._device_procs.items()):
            if proc.poll() is not None and self.state.devices[name] in (
                DEVICE_CONNECTED, DEVICE_CONNECTING,
            ):
                self.state.set_device(name, DEVICE_ERROR, "桥进程已退出")

    def sidebar_config(self) -> dict:
        """Safe subset for ``GET /config`` (no command bodies)."""
        sidebar = self.config.get("sidebar", {})
        return {
            "groups": sidebar.get("groups", []),
            "log": sidebar.get("log"),
            "web_url": self.config.get("web", {}).get("url", "http://localhost:5173"),
        }

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
                return {"ok": True, "message": "系统已在运行或启动中"}
            self.state.set_system(SYSTEM_STARTING, "正在启动…")
        try:
            self._detect_wsl()
            self._sync_files()
            self._spawn_web_services()
            if not self._wait_ready(
                self.config["web"]["url"],
                float(self.config["web"].get("ready_timeout_sec", 60)),
            ):
                raise RuntimeError("网页服务未就绪（超时），请确认前端已启动")
            self.state.set_system(SYSTEM_RUNNING, "系统已就绪")
            return {"ok": True, "message": "系统已启动并就绪"}
        except Exception as exc:
            self.state.set_system(SYSTEM_ERROR, friendly_error(exc, "启动系统"))
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
            f"WSL（{cfg['distro']}）未完全就绪：systemd/共享在 "
            f"{timeout:.0f}s 内未就绪，请检查 WSL 是否正常启动"
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
                raise RuntimeError(f"同步 {rel} 失败（退出码 {result.exit_code}）")

    def _spawn_web_services(self) -> None:
        for cmd in build_start_web_cmds(self.config):
            self._web_procs.append(self.executor.spawn(cmd))

    def _wait_ready(self, url: str, timeout: float) -> bool:
        return self._ready_check(url, timeout)

    def stop_system(self) -> dict:
        """停桥进程 + 停 web 进程 + 停 WSL（§1.3 关闭流程）。"""
        with self._lock:
            if not can_stop_system(self.state):
                return {"ok": True, "message": "系统已停止"}
            self.state.set_system(SYSTEM_STOPPING, "正在停止…")
        try:
            for proc in self._device_procs.values():
                self._terminate_proc(proc)
            self._device_procs.clear()
            for proc in self._web_procs:
                self._terminate_proc(proc)
            self._web_procs.clear()
            if self.config["wsl"].get("stop_wsl", True):
                try:
                    self.executor.run(
                        ["wsl", "--terminate", self.config["wsl"]["distro"]],
                        timeout=30,
                    )
                except Exception:
                    pass  # best-effort: WSL 可能已经关闭
            self.state.set_system(SYSTEM_STOPPED, "系统已停止")
            for name in self.state.devices:
                self.state.set_device(name, DEVICE_DISCONNECTED, "")
            return {"ok": True, "message": "系统已停止"}
        except Exception as exc:
            self.state.set_system(SYSTEM_ERROR, friendly_error(exc, "停止系统"))
            return {"ok": False, "message": self.state.system_msg}

    def restart_web(self) -> dict:
        """停掉旧 web 进程（pkill）并重新拉起。"""
        with self._lock:
            if not can_stop_system(self.state):
                return {"ok": False, "message": "系统未运行，无需重启 web 服务"}
            self.state.set_system(SYSTEM_STARTING, "正在重启 web 服务…")
        try:
            stop_cmd = self.config["web"].get("stop_cmd")
            if stop_cmd:
                self.executor.run(
                    build_wsl_cd_cmd(
                        self.config["wsl"]["distro"],
                        self.config["wsl"]["repo_path"],
                        stop_cmd,
                    ),
                    timeout=30,
                )
            for proc in self._web_procs:
                self._terminate_proc(proc)
            self._web_procs.clear()
            self._spawn_web_services()
            if not self._wait_ready(
                self.config["web"]["url"],
                float(self.config["web"].get("ready_timeout_sec", 60)),
            ):
                raise RuntimeError("网页服务未就绪（超时），请确认前端已启动")
            self.state.set_system(SYSTEM_RUNNING, "系统已就绪")
            return {"ok": True, "message": "web 服务已重启"}
        except Exception as exc:
            self.state.set_system(SYSTEM_ERROR, friendly_error(exc, "重启 web 服务"))
            return {"ok": False, "message": self.state.system_msg}

    # -- M4: device chain -------------------------------------------------

    def connect_device(self, name: str) -> dict:
        with self._lock:
            if name not in self.config["devices"]:
                return {"ok": False, "message": f"未知设备: {name}"}
            if not can_connect_device(self.state):
                return {"ok": False, "message": "系统未就绪，请先启动系统"}
            dev = self.config["devices"][name]
            if self.state.devices[name] in (DEVICE_CONNECTING, DEVICE_CONNECTED):
                return {"ok": True, "message": f"{dev['label']} 已连接"}
            self.state.set_device(name, DEVICE_CONNECTING, "连接中…")
        try:
            dev_type = dev["type"]
            if dev_type == "bridge":
                self._connect_bridge(name, dev)
            elif dev_type == "usbipd":
                self._connect_usbipd(name, dev)
            else:
                raise ValueError(f"未知设备类型: {dev_type!r}")
            self.state.set_device(name, DEVICE_CONNECTED, "已连接")
            return {"ok": True, "message": f"{dev['label']} 已连接"}
        except Exception as exc:
            self.state.set_device(
                name, DEVICE_ERROR, friendly_error(exc, f"连接 {dev['label']}")
            )
            return {"ok": False, "message": self.state.device_msgs[name]}

    def _connect_bridge(self, name: str, dev: dict) -> None:
        """Run the Windows-side LSL bridge; fail if it dies during the
        verify window or the optional verify_cmd does not pass."""
        proc = self.executor.spawn(
            build_bridge_command(dev["command"]), cwd=dev.get("cwd"),
        )
        self._device_procs[name] = proc
        time.sleep(float(dev.get("verify_delay_sec", 5)))
        if proc.poll() is not None:
            raise RuntimeError("桥进程已退出，请确认设备已开机且未被占用")
        verify = dev.get("verify_cmd")
        if verify:
            result = self.executor.run(build_bridge_command(verify), timeout=30)
            if not result.ok():
                raise RuntimeError("设备验证未通过，请检查设备连接")

    def _connect_usbipd(self, name: str, dev: dict) -> None:
        """Attach the Thymio USB device via usbipd, then verify inside WSL."""
        result = self.executor.run(
            build_usbipd_attach_cmd(dev["attach_cmd"]), timeout=30,
        )
        if not result.ok():
            raise RuntimeError(
                f"usbipd attach 失败（退出码 {result.exit_code}）"
                f"{'：' + result.stderr.strip() if result.stderr.strip() else ''}"
            )
        time.sleep(float(dev.get("verify_delay_sec", 3)))
        verify = dev.get("verify_cmd")
        if verify:
            vresult = self.executor.run(build_bridge_command(verify), timeout=30)
            if not vresult.ok():
                raise RuntimeError("设备验证未通过（ttyACM0 不可见）")

    def disconnect_device(self, name: str) -> dict:
        with self._lock:
            if name not in self.config["devices"]:
                return {"ok": False, "message": f"未知设备: {name}"}
            dev = self.config["devices"][name]
            if self.state.devices[name] == DEVICE_DISCONNECTED:
                return {"ok": True, "message": f"{dev['label']} 已断开"}
            self.state.set_device(name, DEVICE_DISCONNECTING, "断开中…")
        try:
            dev_type = dev["type"]
            if dev_type == "bridge":
                self._terminate_proc(self._device_procs.pop(name, None))
            elif dev_type == "usbipd":
                result = self.executor.run(
                    build_usbipd_detach_cmd(dev["detach_cmd"]), timeout=30,
                )
                if not result.ok():
                    raise RuntimeError(
                        f"usbipd detach 失败（退出码 {result.exit_code}）"
                    )
            else:
                raise ValueError(f"未知设备类型: {dev_type!r}")
            self.state.set_device(name, DEVICE_DISCONNECTED, "")
            return {"ok": True, "message": f"{dev['label']} 已断开"}
        except Exception as exc:
            self.state.set_device(
                name, DEVICE_ERROR, friendly_error(exc, f"断开 {dev['label']}")
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
                html = "<html><body><h1>总控页未就绪</h1></body></html>"
            return self._send_html(html)
        if path == "/status":
            return self._send_json(self.server.app.status())
        if path == "/config":
            return self._send_json(self.server.app.sidebar_config())
        return self._send_json({"ok": False, "message": "未知地址"}, code=404)

    def do_POST(self):
        app = self.server.app
        # Finding A: /start-system /stop-system /restart-web and the device
        # POSTs are triggerable as CORS simple requests — any webpage could
        # fire them at the loopback service. Reject cross-origin POSTs.
        if not app.validate_origin(self.headers.get("Origin", "")):
            return self._send_json(
                {"ok": False, "message": "跨域请求被拒绝"}, code=403
            )
        path = urlparse(self.path).path
        try:
            if path == "/start-system":
                result = app.start_system()
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
                return self._send_json({"ok": True, "message": "总控服务已退出"})
            else:
                return self._send_json({"ok": False, "message": "未知接口"}, code=404)
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
        print(f"[ERROR] 无法启动服务（端口 {port} 可能已被占用）: {exc}")
        return 1
    print(f"[INFO] O2 总控服务已启动: http://{host}:{port}/")
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
