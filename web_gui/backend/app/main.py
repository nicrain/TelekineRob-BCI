from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .command_runner import cleanup_residual_processes, start_system, stop_system
from .config_store import get_config_envelope, init_store, patch_config
from .experiment import (
    DEFAULT_PROTOCOL,
    ExperimentSession,
    TrialSpec,
    config_summary,
    load_protocol,
    session_meta_from_request,
    trial_dict,
)
from .logs import RingBufferHandler, tail_files
from .models import (
    CommandRequest,
    ConfigPatch,
    ExperimentConfigureRequest,
)
from .ros_probe import probe_system
from .signal_subscriber import RosBridge

app = FastAPI(title="Thymio Web GUI Backend", version="0.1.0")

# Origin whitelist for CORS + WebSocket. Defaults to the local Vite dev
# server (reachable via both localhost and 127.0.0.1 — the frontend proxies
# /api and /ws to the backend, so the browser's Origin stays on :5173).
# Set WEB_GUI_FRONTEND_ORIGIN to a specific remote origin (e.g.
# "https://eeg.zhaoyu.wang") to lock it down further. An explicit "*" still
# disables the origin check for research convenience, but the Web GUI now
# defaults to a locked-down posture.
_DEFAULT_FRONTEND_ORIGINS = (
    "http://127.0.0.1:5173",
    "https://127.0.0.1:5173",
    "http://localhost:5173",
    "https://localhost:5173",
)

_frontend_origin = os.getenv("WEB_GUI_FRONTEND_ORIGIN", "http://127.0.0.1:5173").strip()
_wildcard_origin = _frontend_origin in ("", "*")

# Control token for robot-driving endpoints. Empty → token auth disabled.
# Set WEB_GUI_CONTROL_TOKEN and pass `Authorization: Bearer <token>` (REST)
# or `?token=<token>` (WebSocket) to use it. CORS does not protect
# WebSockets, so a token is the defence-in-depth for a non-loopback bind.
_control_token = os.getenv("WEB_GUI_CONTROL_TOKEN", "").strip()


def _validate_origin(origin: str) -> bool:
    """Validate origin has http/https scheme and matches allowed list."""
    if _wildcard_origin:
        return True
    if not origin or not isinstance(origin, str):
        return False
    if not (origin.startswith("http://") or origin.startswith("https://")):
        return False
    allowed = set(_DEFAULT_FRONTEND_ORIGINS)
    allowed.add(_frontend_origin)
    return origin in allowed


def _rest_authorized(authorization: str) -> bool:
    """Token gate for REST control endpoints (Authorization: Bearer <token>)."""
    return (not _control_token) or authorization == f"Bearer {_control_token}"


def _ws_authorized(token: str) -> bool:
    """Token gate for control WebSockets (browsers cannot set WS headers)."""
    return (not _control_token) or token == _control_token


async def _reject_invalid_origin(websocket: WebSocket) -> bool:
    """Reject websocket requests from invalid Origin values."""
    if _wildcard_origin:
        return False
    origin = websocket.headers.get("origin", "")
    if _validate_origin(origin):
        return False
    await websocket.close(code=1008, reason="invalid origin")
    return True


_cors_origins = ["*"] if _wildcard_origin else sorted(
    {_frontend_origin, *_DEFAULT_FRONTEND_ORIGINS}
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=not _wildcard_origin,
    allow_methods=["*"],
    allow_headers=["*"],
)

_subscriber: RosBridge | None = None
_experiment = ExperimentSession()
# P17①: recent-log ring for the log panel — captures everything routed to
# root (main/ros_bridge/teleop/... propagate there).
_ring = RingBufferHandler()
logging.getLogger().addHandler(_ring)


def _get_subscriber() -> RosBridge:
    global _subscriber
    if _subscriber is None:
        _subscriber = RosBridge()
    return _subscriber


@app.on_event("startup")
async def _startup() -> None:
    init_store()
    # P16/E1: the experiment recorder receives every raw analysis frame.
    _get_subscriber().add_frame_handler(_experiment.on_frame)


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _subscriber
    if _subscriber is not None:
        _subscriber.stop()
        _subscriber = None
    _log = logging.getLogger("main")
    _log.info(cleanup_residual_processes())


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
def get_config(reload: bool = False) -> dict[str, Any]:
    return get_config_envelope(reload=reload).model_dump()


@app.put("/api/config")
def update_config(req: ConfigPatch) -> dict[str, Any]:
    return patch_config(req.patch).model_dump()


@app.get("/api/config/control_token")
def control_token(request: Request) -> dict[str, str]:
    """Return the configured control token (empty string when unset).

    Only **loopback** clients may read the token (M4-3): the local frontend
    (via the Vite proxy → same-host backend) can, but LAN clients cannot —
    otherwise the token's whole purpose (gating non-browser control calls)
    would be defeated by anyone who can reach this endpoint. ⚠️ verify on
    WSL2 that proxied local access still sees a loopback client.host.
    """
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="control token only readable from loopback")
    return {"token": _control_token}


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    return probe_system().model_dump()


@app.post("/api/system/start")
def api_start(request: Request, req: CommandRequest) -> dict[str, Any]:
    if not _rest_authorized(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="missing or invalid control token")
    cfg = get_config_envelope().config
    return start_system(cfg, dry_run=req.dry_run).model_dump()


@app.post("/api/system/stop")
def api_stop(request: Request, req: CommandRequest) -> dict[str, Any]:
    if not _rest_authorized(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="missing or invalid control token")
    return stop_system(dry_run=req.dry_run).model_dump()


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket) -> None:
    if await _reject_invalid_origin(websocket):
        return
    await websocket.accept()
    try:
        while True:
            frames = _get_subscriber().get_latest_frames()
            payload = {
                # O23: probe_system() runs blocking `which` + /dev globs — keep
                # it off the event loop.
                "status": (await asyncio.to_thread(probe_system)).model_dump(),
                "devices": frames or None,
                "timestamp": time.time(),
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
    if not _ws_authorized(websocket.query_params.get("token", "")):
        await websocket.close(code=1008, reason="unauthorized")
        return
    await websocket.accept()

    cfg = get_config_envelope().config
    use_sim = cfg.launch.use_sim

    # Send initial config so the client knows which topic is in use
    # (informational; the real topic is re-read on every message — O11).
    await websocket.send_json({
        "type": "config",
        "use_sim": use_sim,
        "topic": "/model/thymio/cmd_vel" if use_sim else "/cmd_vel",
    })

    _log = logging.getLogger("teleop")
    bridge = _get_subscriber()
    try:
        while True:
            try:
                msg = await websocket.receive_json()
            except (json.JSONDecodeError, ValueError) as e:
                # O23: malformed JSON must not crash the handler / spam tracebacks.
                await websocket.send_json({"type": "error", "detail": f"invalid JSON: {e}"})
                continue
            direction = msg.get("direction", "")
            # O11: re-read config on every message so a sim ↔ real switch takes
            # effect without reconnecting.
            cfg = get_config_envelope().config
            use_sim = cfg.launch.use_sim
            _log.info("received direction=%s", direction)
            ok, detail = bridge.publish_teleop(direction, use_sim, cfg)
            _log.info("publish direction=%s ok=%s detail=%s", direction, ok, detail)
            await websocket.send_json({
                "type": "ack" if ok else "error",
                "direction": direction,
                "detail": detail,
            })
    except WebSocketDisconnect:
        return


# --------------------------------------------------------------------------- #
# P16: experiment mode (E1 logging / E3 protocol + prompt UI / E4 labels)
# --------------------------------------------------------------------------- #


@app.get("/api/logs")
def get_logs(lines: int = 100) -> dict[str, Any]:
    """P17①: recent backend log records + best-effort WSL launcher log tails."""
    return {"backend": _ring.tail(lines), "files": tail_files(lines)}


@app.get("/api/experiment/protocol")
def exp_protocol() -> dict[str, Any]:
    """The default protocol file (trials + shuffle + prompt_sec) for the
    E3 panel to show before the operator starts."""
    proto = load_protocol(DEFAULT_PROTOCOL)
    return {
        "shuffle": proto["shuffle"],
        "seed": proto["seed"],
        "prompt_sec": proto["prompt_sec"],
        "n_trials": len(proto["trials"]),
        "trials": [trial_dict(t) for t in proto["trials"]],
    }


@app.post("/api/experiment/configure")
def exp_configure(req: ExperimentConfigureRequest) -> dict[str, Any]:
    """Start a session: hand-filled metadata + protocol (inline trials, or the
    default protocol file), shuffle applied, session files opened.

    P20: metric / device_mode are NOT accepted from the client — they are
    derived from the live AppConfig so the recorded truth matches the actual
    run. electrode is only recorded when the config includes a hybrid.
    """
    # P21: the frontend supplies its ACTUAL run config (validated by the
    # pydantic model: literals + device-count + has_hybrid consistency) and
    # it is recorded verbatim into session.json's system block. A direct API
    # caller without a config falls back to the backend AppConfig summary.
    if req.config is not None:
        summary = req.config.model_dump()
    else:
        summary = config_summary(get_config_envelope().config)
    meta = session_meta_from_request(
        subject=req.meta.subject,
        role=req.meta.role,
        session_no=req.meta.session_no,
        electrode=req.meta.electrode,
        date=req.meta.date,
        summary=summary,
    )
    if req.trials is not None:
        trials = [TrialSpec(**t.model_dump()) for t in req.trials]
        shuffle = req.shuffle or "none"
        seed, prompt_sec = req.seed, req.prompt_sec
    else:
        proto = load_protocol(DEFAULT_PROTOCOL)
        trials = proto["trials"]
        shuffle = req.shuffle or proto["shuffle"]
        seed = req.seed if req.seed is not None else proto["seed"]
        prompt_sec = req.prompt_sec if req.prompt_sec is not None else proto["prompt_sec"]
    session_id = _experiment.configure(meta, trials, shuffle, seed, prompt_sec, system_summary=summary)
    return {"ok": True, "session_id": session_id, "state": _experiment.state()}


@app.get("/api/experiment/state")
def exp_state() -> dict[str, Any]:
    # P21: the config display is frontend-real-time (App.jsx 01 props), not a
    # backend poll — state() carries only the trial machine.
    return _experiment.state()


@app.post("/api/experiment/start")
def exp_start() -> dict[str, Any]:
    return {"ok": _experiment.start(), "state": _experiment.state()}


@app.post("/api/experiment/pause")
def exp_pause() -> dict[str, Any]:
    _experiment.pause()
    return {"state": _experiment.state()}


@app.post("/api/experiment/resume")
def exp_resume() -> dict[str, Any]:
    _experiment.resume()
    return {"state": _experiment.state()}


@app.post("/api/experiment/reset")
def exp_reset() -> dict[str, Any]:
    _experiment.reset()
    return {"state": _experiment.state()}


if __name__ == "__main__":
    import uvicorn

    # Default to loopback only: the Web GUI drives a physical robot, so it
    # must not be reachable from the LAN unless the operator explicitly
    # opts in (WEB_GUI_HOST=0.0.0.0 — and then a control token is advised).
    host = os.getenv("WEB_GUI_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_GUI_PORT", "8010"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
