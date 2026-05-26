"""
Single rclpy bridge thread for the web GUI backend.

Subscribes to /eeg_analysis for signal data AND publishes Twist
for teleop — all from one rclpy thread to avoid executor conflicts.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from typing import Any, Optional

_log = logging.getLogger("ros_bridge")

TELEOP_DIRECTIONS = {"forward", "backward", "left", "right", "stop"}


class RosBridge:
    """Background rclpy thread: subscriber + teleop publisher in one node."""

    def __init__(self, analysis_topic: str = "/eeg_analysis", stale_threshold: float = 0.5) -> None:
        self._analysis_topic = analysis_topic
        self._stale_threshold = stale_threshold
        self._lock = threading.Lock()
        self._latest: Optional[dict[str, Any]] = None
        self._last_ts: float = 0.0
        self._msg_count: int = 0
        self._twist_queue: queue.Queue = queue.Queue()
        self._twist_publisher: Any = None
        self._twist_topic: str = ""
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._error: Optional[str] = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="ros_bridge")
        self._thread.start()
        if not self._ready.wait(timeout=10.0):
            _log.warning("RosBridge did not become ready within 10s")
        if self._error:
            _log.error("RosBridge error: %s", self._error)
        _log.info("RosBridge ready=%s", self.ready)

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
        with self._lock:
            if self._latest is None:
                return None
            if time.monotonic() - self._last_ts > self._stale_threshold:
                return None
            return dict(self._latest)

    # ── Teleop ───────────────────────────────────────────────────────────────

    def publish_teleop(self, direction: str, use_sim: bool, cfg: Any) -> tuple[bool, str]:
        """Queue a teleop direction for the rclpy thread to publish. Non-blocking."""
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

        self._ensure_twist_publisher(topic)
        try:
            self._twist_queue.put_nowait((topic, lin, ang))
            return True, f"Published {direction} to {topic}"
        except Exception as e:
            return False, str(e)

    def _ensure_twist_publisher(self, topic: str) -> None:
        """Lazily create the Twist publisher for the given topic."""
        if self._twist_publisher is not None and self._twist_topic == topic:
            return
        self._twist_queue.put(("__create__", topic, 0.0))
        # Wait briefly for the rclpy thread to process the creation request
        deadline = time.monotonic() + 3.0
        while self._twist_publisher is None and time.monotonic() < deadline:
            time.sleep(0.01)

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
            self._rclpy_node.create_subscription(
                String, self._analysis_topic, self._on_analysis, 10
            )
            _log.info("subscribed to %s", self._analysis_topic)
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
                _log.warning("spin_once exception: %s", e)
                break
            self._drain_twist_queue()

        _log.info("spin loop ended")
        self._rclpy_node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass

    def _drain_twist_queue(self) -> None:
        """Process pending teleop Twist publishes in the rclpy thread."""
        from geometry_msgs.msg import Twist

        while True:
            try:
                item = self._twist_queue.get_nowait()
            except queue.Empty:
                return

            topic, a, b = item
            if topic == "__create__":
                # a = topic, b unused — create publisher
                from rclpy.node import Node
                self._twist_publisher = self._rclpy_node.create_publisher(Twist, a, 10)
                self._twist_topic = a
                _log.info("created teleop publisher on %s", a)
            else:
                msg = Twist()
                msg.linear.x = float(a)
                msg.linear.y = 0.0
                msg.linear.z = 0.0
                msg.angular.x = 0.0
                msg.angular.y = 0.0
                msg.angular.z = float(b)
                self._twist_publisher.publish(msg)

    # ── Analysis callback ────────────────────────────────────────────────────

    def _on_analysis(self, msg: Any) -> None:
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
                "asymmetry": float(features.get("alpha_asym", 0)),
            },
            "control": {
                "speed_intent": float(intents.get("speed_intent", 0)),
                "steer_intent": float(intents.get("steer_intent", 0.5)),
            },
            "timestamp": float(data.get("ts", time.time())),
        }

        with self._lock:
            self._latest = frame
            self._last_ts = time.monotonic()
            was_first = self._msg_count == 0
            self._msg_count += 1
            if was_first:
                _log.info("first analysis: alpha=%.3f theta=%.3f beta=%.3f", alpha, theta, beta)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
