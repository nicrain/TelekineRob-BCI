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
import subprocess
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
    build_wsl_detect_cmd,
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

NOT_IMPLEMENTED = "该功能尚未开通"


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
    if isinstance(exc, ValueError):
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

    # -- read endpoints --------------------------------------------------

    def status(self) -> dict:
        return status_payload(self.state)

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

    # -- action stubs (implemented in M3 / M4) ---------------------------

    def start_system(self) -> dict:
        raise NotImplementedError(NOT_IMPLEMENTED)

    def stop_system(self) -> dict:
        raise NotImplementedError(NOT_IMPLEMENTED)

    def restart_web(self) -> dict:
        raise NotImplementedError(NOT_IMPLEMENTED)

    def connect_device(self, name: str) -> dict:
        raise NotImplementedError(NOT_IMPLEMENTED)

    def disconnect_device(self, name: str) -> dict:
        raise NotImplementedError(NOT_IMPLEMENTED)

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
        path = urlparse(self.path).path
        app = self.server.app
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
            else:
                return self._send_json({"ok": False, "message": "未知接口"}, code=404)
        except NotImplementedError as exc:
            result = {"ok": False, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 — operator-facing guard
            result = {"ok": False, "message": friendly_error(exc)}
        return self._send_json(result)


def main(argv: Optional[List[str]] = None) -> int:
    config_path = Path(argv[1]) if argv else DEFAULT_CONFIG
    try:
        config = load_config(config_path)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    host = config["service"].get("host", "127.0.0.1")
    port = int(config["service"].get("port", 8020))
    app = LauncherApp(config)
    server = LauncherServer((host, port), app)
    print(f"[INFO] O2 总控服务已启动: http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
