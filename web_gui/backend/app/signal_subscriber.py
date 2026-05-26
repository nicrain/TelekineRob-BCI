"""
ROS2 subscriber for pipeline signal data → WebSocket bridge.

Runs rclpy in a background thread, subscribes to /eeg_analysis,
and stores the latest frame for the WebSocket /ws/stream endpoint.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Optional


class SignalSubscriber:
    """Background-thread ROS2 subscriber to /eeg_analysis.

    Provides thread-safe access to the most recent analysis frame
    transformed into the web GUI frontend format.
    """

    def __init__(self, topic: str = "/eeg_analysis", stale_threshold: float = 0.5) -> None:
        self._topic = topic
        self._stale_threshold = stale_threshold
        self._lock = threading.Lock()
        self._latest: Optional[dict[str, Any]] = None
        self._last_ts: float = 0.0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._error: Optional[str] = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="rclpy_signal_sub")
        self._thread.start()
        self._ready.wait(timeout=10.0)

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    @property
    def error(self) -> Optional[str]:
        return self._error

    def get_latest_frame(self) -> Optional[dict[str, Any]]:
        """Return the latest frame if fresh, None if stale or never received."""
        with self._lock:
            if self._latest is None:
                return None
            if time.monotonic() - self._last_ts > self._stale_threshold:
                return None
            return dict(self._latest)

    def _run(self) -> None:
        try:
            import rclpy
            from rclpy.node import Node
            from std_msgs.msg import String
        except Exception as e:
            self._error = f"rclpy import failed: {e}"
            self._ready.set()
            return

        try:
            if not rclpy.ok():
                rclpy.init()
        except Exception as e:
            self._error = f"rclpy.init() failed: {e}"
            self._ready.set()
            return

        try:
            self._node = Node("signal_bridge_subscriber")
            self._sub = self._node.create_subscription(
                String, self._topic, self._on_analysis, 10
            )
        except Exception as e:
            self._error = f"ROS2 subscriber setup failed: {e}"
            self._ready.set()
            return

        self._ready.set()

        while not self._stop_event.is_set():
            try:
                rclpy.spin_once(self._node, timeout_sec=0.05)
            except Exception:
                break

        self._node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass

    def _on_analysis(self, msg: Any) -> None:
        """Parse the analysis JSON and store as web GUI format."""
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

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
