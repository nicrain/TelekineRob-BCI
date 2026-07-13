#!/usr/bin/env python3
"""EEG ROS2 control node — g.tec device support.

Uses modular architecture (thymio_control.pipeline + processors.enrich).
"""

import csv
import json
import os
import time
from typing import Optional

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import Range
from std_msgs.msg import String

# --- Modular architecture ---
from thymio_control.pipeline import POLICIES, build_adapter
from thymio_control.processors.enrich import clip01, enrich_features


class _AdapterArgs:
    """Lightweight argument container for build_adapter."""

    def __init__(
        self,
        input_mode: str,
        lsl_stream_type: str,
        lsl_timeout: float,
        lsl_source_id: str,
    ):
        self.input = input_mode
        self.lsl_stream_type = lsl_stream_type
        self.lsl_timeout = lsl_timeout
        self.lsl_source_id = lsl_source_id


class EegControlNode(Node):
    # Maps policy name → the feature key to collect during calibration
    _CALIB_METRIC: dict[str, str] = {
        "tbr":   "theta_beta",
        "ei":    "beta_alpha_theta",
        "alpha": "alpha",
    }

    def __init__(self) -> None:
        super().__init__("eeg_control_node")

        # Input and policy parameters
        self.declare_parameter("input", "lsl")
        self.declare_parameter("policy", "tbr")
        self.declare_parameter("calibrate", False)
        self.declare_parameter("calib_offset", 0.0)
        self.declare_parameter("calib_scale", 1.0)
        self.declare_parameter("lsl_stream_type", "EEG")
        self.declare_parameter("lsl_timeout", 8.0)
        self.declare_parameter("lsl_source_id", "")

        # Output and control parameters
        self.declare_parameter("cmd_topic", "/cmd_vel")
        self.declare_parameter("analysis_topic", "/eeg_analysis")
        self.declare_parameter("publish_hz", 20.0)
        self.declare_parameter("watchdog_sec", 0.5)
        self.declare_parameter("verbose", False)
        self.declare_parameter("analysis_verbose", False)
        self.declare_parameter("record_csv", False)
        self.declare_parameter("csv_path", "/tmp/thymio_eeg_log.csv")

        # Motion mapping parameters
        self.declare_parameter("max_forward_speed", 0.2)
        self.declare_parameter("reverse_speed", -0.15)
        self.declare_parameter("turn_forward_speed", 0.1)
        self.declare_parameter("turn_angular_speed", 1.2)
        self.declare_parameter("reverse_threshold", 0.2)
        self.declare_parameter("steer_deadzone", 0.1)

        # Optional line-following
        self.declare_parameter("line_mode", "")  # '', 'blackline', 'whiteline'

        input_mode = self.get_parameter("input").value
        policy_name = self.get_parameter("policy").value
        if policy_name not in POLICIES:
            valid = ", ".join(sorted(POLICIES.keys()))
            raise RuntimeError(f"Unknown policy: {policy_name!r} (valid: {valid})")

        adapter_args = _AdapterArgs(
            input_mode=input_mode,
            lsl_stream_type=self.get_parameter("lsl_stream_type").value,
            lsl_timeout=float(self.get_parameter("lsl_timeout").value),
            lsl_source_id=self.get_parameter("lsl_source_id").value,
        )
        self.adapter = build_adapter(adapter_args)

        calib_offset = float(self.get_parameter("calib_offset").value)
        calib_scale = float(self.get_parameter("calib_scale").value)
        self._calibrate = bool(self.get_parameter("calibrate").value)
        self._calib_samples: list[float] = []
        self._calib_deadline: float = 0.0

        self.policy = POLICIES[policy_name](offset=calib_offset, scale=calib_scale)

        self.pub = self.create_publisher(Twist, self.get_parameter("cmd_topic").value, 10)
        self.analysis_pub = self.create_publisher(String, self.get_parameter("analysis_topic").value, 10)

        self.watchdog_sec = float(self.get_parameter("watchdog_sec").value)
        self.verbose = bool(self.get_parameter("verbose").value)
        self.analysis_verbose = bool(self.get_parameter("analysis_verbose").value)
        self.record_csv = bool(self.get_parameter("record_csv").value)
        self.csv_path = str(self.get_parameter("csv_path").value)
        self.max_forward_speed = min(1.0, max(0.0, float(self.get_parameter("max_forward_speed").value)))
        self.reverse_speed = min(0.0, max(-1.0, float(self.get_parameter("reverse_speed").value)))
        self.turn_forward_speed = min(1.0, max(0.0, float(self.get_parameter("turn_forward_speed").value)))
        self.turn_angular_speed = min(3.0, max(0.0, float(self.get_parameter("turn_angular_speed").value)))
        self.reverse_threshold = min(1.0, max(0.0, float(self.get_parameter("reverse_threshold").value)))
        self.steer_deadzone = min(1.0, max(0.0, float(self.get_parameter("steer_deadzone").value)))
        self._csv_file = None
        self._csv_writer = None
        self._csv_flush_counter = 0
        self._csv_flush_every_n = 10
        if self.record_csv:
            csv_dir = os.path.dirname(self.csv_path)
            if csv_dir:
                os.makedirs(csv_dir, exist_ok=True)
            self._csv_file = open(self.csv_path, "a", newline="", encoding="utf-8")
            self._csv_writer = csv.DictWriter(
                self._csv_file,
                fieldnames=[
                    "ts",
                    "source",
                    "metrics_json",
                    "command_linear_x",
                    "command_angular_z",
                    "speed_intent",
                    "steer_intent",
                ],
            )
            if self._csv_file.tell() == 0:
                self._csv_writer.writeheader()

        self.line_mode = str(self.get_parameter("line_mode").value).strip() or None
        self.ground = {"left": 0.5, "right": 0.5}
        self.state_dir = 0

        if self.line_mode == "blackline":
            self.on_line = lambda v: v > 0.5
            self.get_logger().info("Line-follow mode: BLACK line")
        elif self.line_mode == "whiteline":
            self.on_line = lambda v: v < 0.5
            self.get_logger().info("Line-follow mode: WHITE line")
        else:
            self.on_line = lambda v: False

        if self.line_mode is not None:
            self.create_subscription(Range, "/ground/left", self._ground_left_cb, 10)
            self.create_subscription(Range, "/ground/right", self._ground_right_cb, 10)

        self.last_msg_ts = 0.0
        self._adapter_connected = False
        self.last_intents = {"speed_intent": 0.5, "steer_intent": 0.5}
        self.last_twist = Twist()

        hz = float(self.get_parameter("publish_hz").value)
        self.create_timer(1.0 / max(hz, 1e-6), self._tick)

        self.get_logger().info(
            (
                f"EEG node started: input={input_mode} policy={policy_name} "
                f"topic={self.get_parameter('cmd_topic').value} analysis_topic={self.get_parameter('analysis_topic').value}"
            )
        )

    def _finish_calibration(self) -> None:
        """Compute p5/p95 from collected samples and update the parameter file."""
        import numpy as np
        import yaml
        import traceback
        from pathlib import Path

        try:
            samples = np.array(self._calib_samples)
            n = len(samples)
            self.get_logger().info(f"CALIB: {n} samples collected")
            if n < 60:
                self.get_logger().error("CALIB: not enough samples — abort")
                return
            p5 = float(np.percentile(samples, 5))
            p95 = float(np.percentile(samples, 95))
            offset = round(p5, 4)
            scale = round(max(p95 - p5, 0.001), 4)

            self.get_logger().info(
                f"CALIB: p5={p5:.4f} p95={p95:.4f} offset={offset} scale={scale}"
            )

            try:
                from rclpy.parameter import Parameter
                self.set_parameters([
                    Parameter("calib_offset", Parameter.Type.DOUBLE, offset),
                    Parameter("calib_scale", Parameter.Type.DOUBLE, scale),
                    Parameter("calibrate", Parameter.Type.BOOL, False),
                ])
            except Exception as exc:
                self.get_logger().warning(
                    f"CALIB: set_parameters() failed (in-memory params not updated): {exc}"
                )

            source_root = Path(__file__).resolve().parents[2]
            install_dir = Path(__file__).parents[2] / "share" / "thymio_control" / "config"
            for cfg_root in [install_dir, source_root / "thymio_control" / "config"]:
                try:
                    cfg_file = cfg_root / "eeg_control_node.params.yaml"
                    with cfg_file.open("r", encoding="utf-8") as fhand:
                        doc = yaml.safe_load(fhand) or {}
                    params = doc.setdefault("/**", {}).setdefault("ros__parameters", {})
                    params["calib_offset"] = offset
                    params["calib_scale"] = scale
                    params["calibrate"] = False
                    with cfg_file.open("w", encoding="utf-8") as fhand:
                        yaml.safe_dump(doc, fhand, sort_keys=False, allow_unicode=False)
                    self.get_logger().info(f"CALIB: wrote {cfg_file}")
                except Exception as exc:
                    self.get_logger().error(
                        f"CALIB: failed to write {cfg_root}: {exc}"
                    )

            policy_name = str(self.get_parameter("policy").value)
            self.policy = POLICIES[policy_name](offset=offset, scale=scale)

        except Exception:
            self.get_logger().error(f"CALIB failed:\n{traceback.format_exc()}")
        finally:
            self._calibrate = False
            self._calib_samples.clear()
            self._calib_deadline = 0.0

    def _close_csv(self) -> None:
        if self._csv_file is not None:
            try:
                self._csv_file.close()
            except Exception as e:
                self.get_logger().error(f"Failed to close CSV file: {e}")
            self._csv_file = None
            self._csv_writer = None

    def _ground_left_cb(self, msg: Range) -> None:
        self.ground["left"] = float(msg.range)

    def _ground_right_cb(self, msg: Range) -> None:
        self.ground["right"] = float(msg.range)

    def _tick(self) -> None:
        frame = self.adapter.read_frame()
        if frame is not None:
            has_band_features = all(key in frame.metrics for key in ("alpha", "theta", "beta"))
            features = enrich_features(frame.metrics) if has_band_features else dict(frame.metrics)

            if self._calibrate and has_band_features:
                calib_key = self._CALIB_METRIC.get(str(self.get_parameter("policy").value))
                if calib_key and calib_key in features:
                    self._calib_samples.append(float(features[calib_key]))
                if self._calib_deadline == 0.0:
                    self._calib_deadline = time.time() + 30.0
                    self.get_logger().info(
                        f"CALIB: collecting samples for metric={calib_key} (30s)"
                    )
                if time.time() >= self._calib_deadline:
                    self._finish_calibration()

            if has_band_features:
                self.last_intents = self.policy.compute_intents(features)
            else:
                self.last_intents = {"speed_intent": 0.5, "steer_intent": 0.5}
            self.last_msg_ts = time.time()
            self._adapter_connected = True

            analysis = {
                "ts": frame.ts,
                "source": frame.source,
                "metrics": frame.metrics,
                "features": features,
                "intents": self.last_intents,
                "control_mode": "band_features",
                "command_linear_x": 0.0,
                "command_angular_z": 0.0,
            }
            self.analysis_pub.publish(String(data=json.dumps(analysis, ensure_ascii=False)))
            if self.analysis_verbose:
                self.get_logger().info(json.dumps(analysis, ensure_ascii=False))

            if self._csv_writer is not None:
                row = {
                    "ts": frame.ts,
                    "source": frame.source,
                    "metrics_json": json.dumps(frame.metrics, ensure_ascii=False, sort_keys=True),
                    "command_linear_x": 0.0,
                    "command_angular_z": 0.0,
                    "speed_intent": self.last_intents.get("speed_intent", 0.5),
                    "steer_intent": self.last_intents.get("steer_intent", 0.5),
                }
                self._csv_writer.writerow(row)
                self._csv_flush_counter += 1
                if self._csv_flush_counter >= self._csv_flush_every_n:
                    self._csv_file.flush()
                    self._csv_flush_counter = 0

            if not self._calibrate:
                self.pub.publish(self._intents_to_twist(self.last_intents))

            if self.verbose:
                self.get_logger().info(
                    "src=%s speed_intent=%.3f steer_intent=%.3f"
                    % (
                        frame.source,
                        self.last_intents.get("speed_intent", 0.5),
                        self.last_intents.get("steer_intent", 0.5),
                    )
                )
            return

        if time.time() - self.last_msg_ts > self.watchdog_sec:
            if self._adapter_connected:
                self._adapter_connected = False
                self.pub.publish(Twist())
            return

        if not self._calibrate:
            self.pub.publish(self._intents_to_twist(self.last_intents))
    def _intents_to_twist(self, intents) -> Twist:
        speed_intent = clip01(float(intents.get("speed_intent", 0.0)))
        steer_intent = clip01(float(intents.get("steer_intent", 0.5)))

        twist = Twist()
        if self.line_mode is not None:
            left_on = self.on_line(self.ground["left"])
            right_on = self.on_line(self.ground["right"])
            speed = self.max_forward_speed * speed_intent

            if speed > 0.01:
                if left_on and right_on:
                    self.state_dir = 0
                elif (not left_on) and right_on:
                    self.state_dir = 1
                elif left_on and (not right_on):
                    self.state_dir = -1
                else:
                    if self.state_dir > 0:
                        self.state_dir = 2
                    elif self.state_dir < 0:
                        self.state_dir = -2
                    else:
                        self.state_dir = 10

                w_pivot = speed * 8.0
                w_spin = speed * 15.0
                if self.state_dir == 0:
                    twist.linear.x = speed
                elif self.state_dir == 1:
                    twist.linear.x = speed / 2.0
                    twist.angular.z = -w_pivot
                elif self.state_dir == -1:
                    twist.linear.x = speed / 2.0
                    twist.angular.z = w_pivot
                elif self.state_dir == 2:
                    twist.angular.z = -w_spin
                elif self.state_dir == -2:
                    twist.angular.z = w_spin
                else:
                    twist.angular.z = -w_spin
        else:
            twist.linear.x = self.max_forward_speed * speed_intent
            steer = (steer_intent - 0.5) * 2.0
            if abs(steer) >= self.steer_deadzone:
                twist.angular.z = -self.turn_angular_speed * steer

        return twist


def main(args: Optional[list] = None) -> None:
    rclpy.init(args=args)
    node = EegControlNode()
    try:
        rclpy.spin(node)
    finally:
        node._close_csv()
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
