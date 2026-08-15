"""System + device state machine for the O2 launcher.

Pure (no IO) so the state rules are unit-testable on any machine.  The
server mutates a :class:`LauncherState` and always returns the payload via
:func:`status_payload`, keeping "what is the truth" separate from "how the
web page displays it".
"""
from __future__ import annotations

from typing import Dict

# --- System states ------------------------------------------------------
SYSTEM_STOPPED = "stopped"
SYSTEM_STARTING = "starting"
SYSTEM_RUNNING = "running"
SYSTEM_STOPPING = "stopping"
SYSTEM_ERROR = "error"

# --- Device states ------------------------------------------------------
DEVICE_DISCONNECTED = "disconnected"
DEVICE_CONNECTING = "connecting"
DEVICE_CONNECTED = "connected"
DEVICE_DISCONNECTING = "disconnecting"
DEVICE_ERROR = "error"


class LauncherState:
    """Mutable truth for the whole launcher (one instance per service)."""

    def __init__(self, device_names: list[str]) -> None:
        self.system = SYSTEM_STOPPED
        self.system_msg = ""
        self.devices: Dict[str, str] = {n: DEVICE_DISCONNECTED for n in device_names}
        self.device_msgs: Dict[str, str] = {n: "" for n in device_names}
        # P42: LAN portproxy health — ok | stale | unresolved (the status area
        # shows the one-click fix prompt only while stale).
        self.lan_forward = "ok"

    # --- mutators (server calls these after IO succeeds/fails) ----------

    def set_system(self, state: str, message: str = "") -> None:
        self.system = state
        self.system_msg = message

    def set_device(self, name: str, state: str, message: str = "") -> None:
        self.devices[name] = state
        self.device_msgs[name] = message


# --- Guards (pure rules the server enforces before acting) --------------

def can_start_system(state: LauncherState) -> bool:
    """Start only from a cold or failed state (idempotent, §4)."""
    return state.system in (SYSTEM_STOPPED, SYSTEM_ERROR)


def can_connect_device(state: LauncherState) -> bool:
    """Device buttons stay disabled until the system is up (§1.3)."""
    return state.system in (SYSTEM_STARTING, SYSTEM_RUNNING)


def can_stop_system(state: LauncherState) -> bool:
    return state.system in (SYSTEM_STARTING, SYSTEM_RUNNING, SYSTEM_ERROR)


# --- Payload ------------------------------------------------------------

def status_payload(state: LauncherState) -> dict:
    """Shape for ``GET /status`` (consumed by the sidebar)."""
    return {
        "system": {"state": state.system, "message": state.system_msg},
        "devices": {
            name: {"state": st, "message": state.device_msgs[name]}
            for name, st in state.devices.items()
        },
        "lan_forward": state.lan_forward,   # P42: ok | stale | unresolved
    }
