"""
Single rclpy bridge thread for the web GUI backend.

Subscribes to the three analysis topics (/eeg_analysis + role-suffixed)
for signal data AND publishes Twist for teleop — all from one rclpy
thread to avoid executor conflicts. publish_teleop only enqueues (O20).
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from functools import partial
from typing import Any, Optional

_log = logging.getLogger("ros_bridge")

TELEOP_DIRECTIONS = {"forward", "backward", "left", "right", "stop"}

# Three analysis topics are always subscribed (design §5.4.4): in single-device
# mode only the bare topic carries data, in dual-device mode only the two
# role-suffixed ones do. No resubscription needed when the mode changes.
DEFAULT_ANALYSIS_TOPICS = [
    "/eeg_analysis",
    "/eeg_analysis/speed",
    "/eeg_analysis/steering",
]


class RosBridge:
    """Background rclpy thread: subscriber + teleop publisher in one node."""

    def __init__(
        self,
        analysis_topics: Optional[list[str]] = None,
        stale_threshold: float = 0.5,
        role_by_topic: Optional[dict[str, str]] = None,
    ) -> None:
        self._analysis_topics = analysis_topics or list(DEFAULT_ANALYSIS_TOPICS)
        # Fallback role per topic when a frame has no ``role`` field (legacy
        # pre-M2 node). The M2 node always emits ``role``, so this is a backstop.
        self._role_by_topic = role_by_topic or {}
        self._stale_threshold = stale_threshold
        self._lock = threading.Lock()
        self._latest: dict[str, dict[str, Any]] = {}
        self._last_ts: dict[str, float] = {}
        self._msg_count: int = 0
        self._twist_queue: queue.Queue = queue.Queue()
        self._twist_publisher: Any = None
        self._twist_topic: str = ""
        self._twist_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._error: Optional[str] = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="ros_bridge")
        self._thread.start()

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def msg_count(self) -> int:
        with self._lock:
            return self._msg_count

    # ── Signal data ──────────────────────────────────────────────────────────

    def get_latest_frame(self) -> Optional[dict[str, Any]]:
        """Single-device compatibility entry: the latest bare /eeg_analysis frame."""
        with self._lock:
            frame = self._latest.get("/eeg_analysis")
            if frame is None:
                return None
            if time.monotonic() - self._last_ts.get("/eeg_analysis", 0.0) > self._stale_threshold:
                return None
            return dict(frame)

    def get_latest_frames(self) -> dict[str, dict[str, Any]]:
        """Fresh analysis frames keyed by device role (``{"speed": {...}}``).

        Only frames received within ``stale_threshold`` are returned. Role
        resolution: the frame's own ``role`` field (M2+) → topic suffix →
        constructor ``role_by_topic`` backstop.
        """
        with self._lock:
            now = time.monotonic()
            out: dict[str, dict[str, Any]] = {}
            for topic, frame in self._latest.items():
                if now - self._last_ts.get(topic, 0.0) > self._stale_threshold:
                    continue
                out[self._resolve_role(topic, frame)] = dict(frame)
            return out

    def _resolve_role(self, topic: str, frame: dict[str, Any]) -> str:
        role = frame.get("role")
        if role in ("speed", "steering"):
            return role
        suffix = topic.rsplit("/", 1)[-1]
        if suffix in ("speed", "steering"):
            return suffix
        fallback = self._role_by_topic.get(topic)
        if fallback in ("speed", "steering"):
            return fallback
        return "speed"

    # ── Teleop ───────────────────────────────────────────────────────────────

    def publish_teleop(self, direction: str, use_sim: bool, cfg: Any) -> tuple[bool, str]:
        """Enqueue a teleop direction for the rclpy thread — never publishes
        directly from the caller's thread (O20: keeps every rclpy call on the
        single bridge thread). Truly non-blocking.

        If the topic changed since the last create, a create request is queued
        first (the rclpy thread destroys the old publisher — O24), then the
        teleop message. Both are processed in order.
        """
        if self._error:
            return False, f"Bridge unavailable: {self._error}"
        if not self._ready.is_set():
            return False, "Bridge not yet ready"
        if direction not in TELEOP_DIRECTIONS:
            return False, f"Unknown direction: {direction!r}"

        topic = "/model/thymio/cmd_vel" if use_sim else "/cmd_vel"
        m = cfg.motion

        if direction == "stop":
            lin, ang = (0.0, 0.0)
        elif direction == "forward":
            lin, ang = (m.max_forward_speed, 0.0)
        elif direction == "backward":
            lin, ang = (m.reverse_speed, 0.0)
        elif direction == "left":
            lin, ang = (m.turn_forward_speed, m.turn_angular_speed)
        elif direction == "right":
            lin, ang = (m.turn_forward_speed, -m.turn_angular_speed)
        else:
            lin, ang = (0.0, 0.0)

        with self._twist_lock:
            topic_changed = self._twist_topic != topic
        if topic_changed:
            self._twist_queue.put(("__create__", topic, 0.0))
        self._twist_queue.put(("__teleop__", topic, lin, ang))
        return True, f"Queued {direction} to {topic}"

    # ── Thread ───────────────────────────────────────────────────────────────

    def _run(self) -> None:
        try:
            import rclpy
            from geometry_msgs.msg import Twist
            from rclpy.node import Node
            from std_msgs.msg import String
        except Exception as e:
            self._error = f"rclpy import failed: {e}"
            _log.warning("%s", self._error)
            self._ready.set()
            return

        try:
            if not rclpy.ok():
                _log.info("rclpy.init() ...")
                rclpy.init()
                _log.info("rclpy.init() done")
        except Exception as e:
            self._error = f"rclpy.init() failed: {e}"
            _log.warning("%s", self._error)
            self._ready.set()
            return

        try:
            self._rclpy_node = Node("web_gui_bridge")
            for topic in self._analysis_topics:
                self._rclpy_node.create_subscription(
                    String, topic, partial(self._on_analysis, topic), 10
                )
            _log.info("subscribed to %s", ", ".join(self._analysis_topics))
        except Exception as e:
            self._error = f"ROS2 node setup failed: {e}"
            _log.warning("%s", self._error)
            self._ready.set()
            return

        self._ready.set()
        _log.info("spinning")

        while not self._stop_event.is_set():
            try:
                rclpy.spin_once(self._rclpy_node, timeout_sec=0.02)
            except Exception as e:
                # O18: record the failure — otherwise /api/health keeps
                # reporting ready while teleop is silently dead.
                self._error = f"spin_once failed: {e}"
                _log.warning("%s", self._error)
                break
            self._drain_twist_queue()

        _log.info("spin loop ended")
        self._rclpy_node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass

    def _drain_twist_queue(self) -> None:
        """Process publisher creation and teleop requests in the rclpy thread."""
        from geometry_msgs.msg import Twist

        while True:
            try:
                item = self._twist_queue.get_nowait()
            except queue.Empty:
                return

            _tag, topic, *_rest = item
            if _tag == "__create__":
                if self._twist_publisher is not None:
                    # O24: destroy the old publisher — switching sim ↔ real
                    # topics repeatedly used to leak rclpy publisher objects.
                    self._rclpy_node.destroy_publisher(self._twist_publisher)
                    self._twist_publisher = None
                self._twist_publisher = self._rclpy_node.create_publisher(Twist, topic, 10)
                with self._twist_lock:
                    self._twist_topic = topic
                _log.info("created teleop publisher on %s", topic)
            elif _tag == "__teleop__":
                with self._twist_lock:
                    topic_ok = self._twist_topic == topic
                if not topic_ok:
                    # Stale teleop for a topic that was switched away (O24):
                    # don't silently publish to the wrong topic.
                    _log.warning("dropped stale teleop for %s (current %s)", topic, self._twist_topic)
                    continue
                if self._twist_publisher is not None:
                    lin, ang = _rest[0], _rest[1]
                    msg = Twist()
                    msg.linear.x = float(lin)
                    msg.linear.y = 0.0
                    msg.linear.z = 0.0
                    msg.angular.x = 0.0
                    msg.angular.y = 0.0
                    msg.angular.z = float(ang)
                    self._twist_publisher.publish(msg)

    # ── Analysis callback ────────────────────────────────────────────────────

    def _on_analysis(self, topic: str, msg: Any) -> None:
        try:
            data = json.loads(msg.data)
        except (json.JSONDecodeError, AttributeError):
            return

        metrics = data.get("metrics", {})
        features = data.get("features", {})
        intents = data.get("intents", {})

        alpha = float(metrics.get("alpha", 0))
        theta = float(metrics.get("theta", 0))
        beta = float(metrics.get("beta", 0))

        frame = {
            "channels": {
                "alpha": alpha,
                "theta": theta,
                "beta": beta,
                "left_alpha": float(metrics.get("left_alpha", alpha * 0.5)),
                "right_alpha": float(metrics.get("right_alpha", alpha * 0.5)),
            },
            "features": {
                "theta_beta_ratio": float(features.get("theta_beta", 0)),
                "focus_index": float(features.get("beta_alpha_theta", 0)),
            },
            "control": {
                "speed_intent": float(intents.get("speed_intent", 0)),
                "steer_intent": float(intents.get("steer_intent", 0.5)),
                "steer_direction": int(data.get("steer_direction", 0)),
            },
            "timestamp": float(data.get("ts", time.time())),
        }

        with self._lock:
            self._latest[topic] = frame
            self._last_ts[topic] = time.monotonic()
            was_first = self._msg_count == 0
            self._msg_count += 1
            if was_first:
                _log.info("first analysis: alpha=%.3f theta=%.3f beta=%.3f", alpha, theta, beta)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
