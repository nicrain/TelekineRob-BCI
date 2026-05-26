from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .command_runner import start_system, stop_system
from .config_store import get_config_envelope, init_store, patch_config
from .models import CommandRequest, ConfigPatch
from .ros_probe import probe_system
from .signal_subscriber import SignalSubscriber
from .teleop_publisher import (
    IS_LINUX,
    ensure_publisher,
    publish_twist_async,
    TELEOP_DIRECTIONS,
)

app = FastAPI(title="Thymio Web GUI Backend", version="0.1.0")

frontend_origin = os.getenv("WEB_GUI_FRONTEND_ORIGIN", "http://localhost:5173")

def _validate_origin(origin: str) -> bool:
    """Validate origin has http/https scheme and matches allowed list."""
    if not origin or not isinstance(origin, str):
        return False
    if not (origin.startswith("http://") or origin.startswith("https://")):
        return False
    allowed = [frontend_origin, "http://127.0.0.1:5173", "https://127.0.0.1:5173"]
    return origin in allowed


async def _reject_invalid_origin(websocket: WebSocket) -> bool:
    """Reject websocket requests from invalid Origin values."""
    origin = websocket.headers.get("origin", "")
    if _validate_origin(origin):
        return False
    await websocket.close(code=1008, reason="invalid origin")
    return True

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin, "http://127.0.0.1:5173", "https://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_subscriber: SignalSubscriber | None = None


def _get_subscriber() -> SignalSubscriber:
    global _subscriber
    if _subscriber is None:
        _subscriber = SignalSubscriber()
    return _subscriber


@app.on_event("startup")
async def _startup() -> None:
    init_store()
    _get_subscriber()


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _subscriber
    if _subscriber is not None:
        _subscriber.stop()
        _subscriber = None


@app.get("/api/health")
def health() -> dict[str, Any]:
    sub = _get_subscriber()
    return {
        "ok": True,
        "subscriber_ready": sub.ready,
        "subscriber_error": sub.error,
        "subscriber_msgs": sub.msg_count,
    }


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return get_config_envelope().model_dump()


@app.put("/api/config")
def update_config(req: ConfigPatch) -> dict[str, Any]:
    return patch_config(req.patch).model_dump()


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    return probe_system().model_dump()


@app.post("/api/system/start")
def api_start(req: CommandRequest) -> dict[str, Any]:
    cfg = get_config_envelope().config
    return start_system(cfg, dry_run=req.dry_run).model_dump()


@app.get("/api/files/tcp")
async def list_tcp_files() -> dict[str, Any]:
    """Return list of available TCP data files for playback."""
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[3]
    tcp_dir = repo_root / "records"
    if not tcp_dir.exists():
        return {"files": []}
    txt_files = sorted([
        f.name for f in tcp_dir.iterdir()
        if f.is_file() and f.suffix == ".txt"
    ])
    return {"files": txt_files}


DATA_EXTENSIONS = {".easy", ".edf", ".txt", ".csv"}


@app.get("/api/files/records")
async def list_record_files() -> dict[str, Any]:
    """Return list of all data files in records/ directory."""
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[3]
    records_dir = repo_root / "records"
    if not records_dir.exists():
        return {"files": []}
    files = sorted([
        f.name for f in records_dir.iterdir()
        if f.is_file() and f.suffix.lower() in DATA_EXTENSIONS
    ])
    return {"files": files}


@app.post("/api/system/stop")
def api_stop(req: CommandRequest) -> dict[str, Any]:
    return stop_system(dry_run=req.dry_run).model_dump()


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket) -> None:
    if await _reject_invalid_origin(websocket):
        return
    await websocket.accept()
    try:
        while True:
            frame = _get_subscriber().get_latest_frame()
            payload = {
                "status": probe_system().model_dump(),
                "channels": frame["channels"] if frame else None,
                "features": frame["features"] if frame else None,
                "control": frame["control"] if frame else None,
                "timestamp": frame["timestamp"] if frame else None,
            }
            await websocket.send_json(payload)
            await asyncio.sleep(0.2)
    except (WebSocketDisconnect, asyncio.CancelledError):
        return


# --------------------------------------------------------------------------- #
# /ws/gazebo_frame — proxies frames from the Gazebo camera bridge node
# (ros2 run thymio_web_bridge gazebo_camera_bridge → ws://127.0.0.1:8011)
# Frontend connects here to avoid CORS and direct port exposure.
# --------------------------------------------------------------------------- #
CAMERA_BRIDGE_URL = os.getenv("CAMERA_BRIDGE_URL", "ws://127.0.0.1:8011/ws/gazebo_frame")


@app.websocket("/ws/gazebo_frame")
async def ws_gazebo_frame(websocket: WebSocket) -> None:
    """Proxy WebSocket → upstream camera bridge with exponential backoff.
    Falls back gracefully if bridge is not running (e.g. Gazebo not started yet)."""
    if await _reject_invalid_origin(websocket):
        return
    await websocket.accept()
    backoff = 0.1  # Start with 100ms backoff
    try:
        import websockets
        while True:
            try:
                async with websockets.connect(CAMERA_BRIDGE_URL, ping_interval=None) as upstream:
                    backoff = 0.1  # Reset on successful connection
                    while True:
                        data = await upstream.recv()
                        if isinstance(data, bytes):
                            await websocket.send_bytes(data)
                        else:
                            await websocket.send_text(data)
            except websockets.exceptions.InvalidURI:
                await websocket.send_json({"error": "camera_bridge_unavailable"})
                return
            except (OSError, websockets.exceptions.ConnectionClosedError):
                backoff = min(backoff * 2, 30.0)  # Exponential backoff, max 30s
                await asyncio.sleep(backoff)
    except WebSocketDisconnect:
        return


# --------------------------------------------------------------------------- #
# /ws/teleop — receives directional commands from the web UI and publishes
# Twist messages to /cmd_vel (real robot) or /model/thymio/cmd_vel (sim).
# Expected message format: { "direction": "forward" | "backward" | "left" | "right" | "stop" }
# --------------------------------------------------------------------------- #


@app.websocket("/ws/teleop")
async def ws_teleop(websocket: WebSocket) -> None:
    """WebSocket teleop endpoint: receives direction commands and publishes Twist."""
    if await _reject_invalid_origin(websocket):
        return
    await websocket.accept()

    cfg = get_config_envelope().config
    use_sim = cfg.launch.use_sim

    # Send initial config so the client knows which topic is in use.
    await websocket.send_json({
        "type": "config",
        "use_sim": use_sim,
        "topic": "/model/thymio/cmd_vel" if use_sim else "/cmd_vel",
    })

    # Kick off publisher and wait for it to be ready before processing commands
    _log = logging.getLogger("teleop")
    pub = ensure_publisher(use_sim, cfg)
    _log.info("publisher ready=%s use_subprocess=%s error=%s", pub.ready, getattr(pub, "_use_subprocess", None), pub.error)
    if not pub.ready:
        ok = pub.wait_ready(timeout=10.0)
        if not ok:
            await websocket.send_json({
                "type": "error",
                "detail": "Publisher failed to start: " + (pub.error or "unknown error"),
            })
            return

    _log = logging.getLogger("teleop")
    try:
        while True:
            msg = await websocket.receive_json()
            direction = msg.get("direction", "")
            _log.info("received direction=%s", direction)
            if direction not in TELEOP_DIRECTIONS:
                await websocket.send_json({
                    "type": "error",
                    "detail": f"Unknown direction: {direction!r}. "
                              f"Valid: {sorted(TELEOP_DIRECTIONS)}",
                })
                continue

            ok, detail = await publish_twist_async(direction, use_sim, cfg)
            _log.info("publish direction=%s ok=%s detail=%s", direction, ok, detail)
            await websocket.send_json({
                "type": "ack" if ok else "error",
                "direction": direction,
                "detail": detail,
            })
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8010, reload=False)
