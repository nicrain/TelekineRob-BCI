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
try:
    from thymio_msgs.msg import Led as ThymioLed  # type: ignore
except ImportError:
    ThymioLed = None  # thymio_msgs not installed (e.g. simulation)

# --- Modular architecture ---
from thymio_control.pipeline import POLICIES, build_adapter
from thymio_control.processors.enrich import clip01, enrich_features
from thymio_control.watchdog import decide_watchdog_action


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
        self.declare_parameter("calib_config_file", "eeg_control_node.params.yaml")
        self.declare_parameter("lsl_stream_type", "EEG")
        self.declare_parameter("lsl_timeout", 8.0)
        self.declare_parameter("lsl_source_id", "")
        self.declare_parameter("role", "speed")

        # Output and control parameters
        self.declare_parameter("cmd_topic", "/cmd_vel")
        self.declare_parameter("analysis_topic", "/eeg_analysis")
        self.declare_parameter("publish_hz", 20.0)
        self.declare_parameter("watchdog_sec", 0.5)
        # Dual-device: stop publishing partial twists on data loss so the
        # fuser sees staleness instead of stale-replayed commands.
        self.declare_parameter("stop_on_data_loss", False)
        self.declare_parameter("verbose", False)
        self.declare_parameter("analysis_verbose", False)
        self.declare_parameter("record_csv", False)
        self.declare_parameter("csv_path", "/tmp/thymio_eeg_log.csv")

        # Motion mapping parameters
        self.declare_parameter("max_forward_speed", 0.05)
        self.declare_parameter("reverse_speed", -0.15)
        self.declare_parameter("turn_angular_speed", 0.8)
        self.declare_parameter("steer_deadzone", 0.1)
        self.declare_parameter("blink_holdoff_frames", 4)
        self.declare_parameter("blink_confirm_frames", 2)

        # Optional line-following
        self.declare_parameter("line_mode", "")  # '', 'blackline', 'whiteline'
        self.declare_parameter("line_pivot_gain", 8.0)
        self.declare_parameter("line_spin_gain", 15.0)

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
        self._calib_config_file = str(self.get_parameter("calib_config_file").value)
        self._calib_samples: list[float] = []
        self._calib_deadline: float = 0.0

        self.policy = POLICIES[policy_name](offset=calib_offset, scale=calib_scale)

        self.pub = self.create_publisher(Twist, self.get_parameter("cmd_topic").value, 10)
        self.analysis_pub = self.create_publisher(String, self.get_parameter("analysis_topic").value, 10)

        # Parse robustly: launch may hand over a "true"/"false" string (from
        # a PythonExpression) or a native bool.
        self.stop_on_data_loss = str(
            self.get_parameter("stop_on_data_loss").value
        ).lower() in {"1", "true", "yes", "on"}

        # Circle LED publisher for steering direction indication
        self._led_circle = None
        if ThymioLed is not None:
            self._led_circle = self.create_publisher(ThymioLed, "/led", 10)
        self.watchdog_sec = float(self.get_parameter("watchdog_sec").value)
        self.verbose = bool(self.get_parameter("verbose").value)
        self.analysis_verbose = bool(self.get_parameter("analysis_verbose").value)
        self.record_csv = bool(self.get_parameter("record_csv").value)
        self.csv_path = str(self.get_parameter("csv_path").value)
        self.max_forward_speed = min(1.0, max(0.0, float(self.get_parameter("max_forward_speed").value)))
        self.reverse_speed = min(0.0, max(-1.0, float(self.get_parameter("reverse_speed").value)))
        self.turn_angular_speed = min(3.0, max(0.0, float(self.get_parameter("turn_angular_speed").value)))
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
        self.line_pivot_gain = float(self.get_parameter("line_pivot_gain").value)
        self.line_spin_gain = float(self.get_parameter("line_spin_gain").value)
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
        self._steer_role = str(self.get_parameter("role").value) == "steering"
        self.steer_direction = 1   # 1 = right, -1 = left (blink toggles)
        self._blink_holdoff = 0
        self._blink_holdoff_frames = int(self.get_parameter("blink_holdoff_frames").value)

        # Metric-based blink confirmation: raw-signal blink candidates must
        # also show a corresponding spike/drop in the policy metric.
        # Uses calibration p5 / p50 (median) as the normal-range reference.
        # EI is inverted (blink → denominator up → EI below p5);
        # TBR/Alpha spike upward (blink → theta/alpha above p50_ref).
        self._metric_key = self._CALIB_METRIC.get(policy_name, "")
        self._metric_inverse = (policy_name == "ei")
        self._blink_confirm_frames = int(self.get_parameter("blink_confirm_frames").value)
        self._metric_blink_counter = 0
        self._last_clean_features: dict = {}

        hz = float(self.get_parameter("publish_hz").value)
        self.create_timer(1.0 / max(hz, 1e-6), self._tick)

        self.get_logger().info(
            (
                f"EEG node started: input={input_mode} policy={policy_name} "
                f"topic={self.get_parameter('cmd_topic').value} analysis_topic={self.get_parameter('analysis_topic').value}"
            )
        )

    def _confirm_blink_metric(self, features: dict) -> bool:
        """Check that the policy metric exceeds its calibrated normal range.

        Calibration stores offset=p5 and scale=p50−p5, so ``offset + scale``
        is the p50 (median) reference — not p95. The naming reflects that.

        TBR / Alpha: blink EOG inflates theta or alpha → metric spikes
        above the median reference.  Check: ``metric > p50_ref × 2``.

        EI: blink inflates alpha + theta (denominator) → EI drops below
        p5.  Check: ``metric < p5 / 2``.
        """
        val = features.get(self._metric_key, None)
        if val is None:
            return False
        val = float(val)

        offset = float(self.get_parameter("calib_offset").value)
        scale  = float(self.get_parameter("calib_scale").value)
        p5      = offset
        p50_ref = offset + scale

        if self._metric_inverse:
            confirmed = val < p5 / 2.0
            ref = f"p5={p5:.3f} p5/2={p5 / 2:.3f}"
        else:
            confirmed = val > p50_ref * 2.0
            ref = f"p50_ref={p50_ref:.3f} p50_ref*2={p50_ref * 2:.3f}"

        if confirmed:
            self.get_logger().info(
                f"Blink metric confirmed: {self._metric_key}={val:.3f} "
                f"({ref})"
            )
        return confirmed

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
            p50 = float(np.percentile(samples, 50))
            offset = round(p5, 4)
            scale = round(max(p50 - p5, 0.001), 4)

            self.get_logger().info(
                f"CALIB: p5={p5:.4f} p50={p50:.4f} offset={offset} scale={scale}"
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
                    cfg_file = cfg_root / self._calib_config_file
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

            # Update offset/scale in place — rebuilding the policy instance
            # would reset its EMA smoothing state and cause an intent jump
            # immediately after calibration.
            self.policy.set_calibration(offset=offset, scale=scale)

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
        self._update_leds()
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

            # Metric-based blink detection — requires metric to stay outside
            # the calibrated normal range for N consecutive frames.
            # Single-frame spikes (noise/artifact) are rejected by the counter.
            # Skipped while calibrating: the pre-calibration thresholds are
            # meaningless and would spuriously toggle steer direction.
            if (
                self._steer_role
                and has_band_features
                and not self._calibrate
                and self._blink_holdoff == 0
            ):
                if self._confirm_blink_metric(features):
                    self._metric_blink_counter += 1
                    if self._metric_blink_counter >= self._blink_confirm_frames:
                        self.steer_direction *= -1  # toggle left ↔ right
                        self._blink_holdoff = self._blink_holdoff_frames
                        self._metric_blink_counter = 0
                        self.get_logger().info(
                            f"Blink detected — steer: {'RIGHT' if self.steer_direction > 0 else 'LEFT'}"
                        )
                else:
                    self._metric_blink_counter = 0

            # Skip policy during hold-off AND while blink counter is
            # accumulating — EOG already contaminates the Welch window
            # before the metric reaches the 2-frame threshold.
            in_blink = self._blink_holdoff > 0 or self._metric_blink_counter > 0

            if self._blink_holdoff > 0:
                self._blink_holdoff -= 1
            elif has_band_features and not in_blink:
                self.last_intents = self.policy.compute_intents(features)
                self._last_clean_features = features
            elif not has_band_features:
                self.last_intents = {"speed_intent": 0.5, "steer_intent": 0.5}

            self.last_msg_ts = time.time()
            self._adapter_connected = True

            # Compute twist first so analysis includes actual command values
            twist = self._intents_to_twist(self.last_intents)

            # Use clean features during hold-off to avoid showing EOG-
            # contaminated spikes in the web GUI charts.
            show_features = features
            if self._blink_holdoff > 0 and self._last_clean_features:
                show_features = self._last_clean_features

            analysis = {
                "ts": frame.ts,
                "source": frame.source,
                "role": "steering" if self._steer_role else "speed",
                "metrics": frame.metrics,
                "features": show_features,
                "intents": self.last_intents,
                "control_mode": "band_features",
                "command_linear_x": twist.linear.x,
                "command_angular_z": twist.angular.z,
                "steer_direction": self.steer_direction,
            }
            self.analysis_pub.publish(String(data=json.dumps(analysis, ensure_ascii=False)))
            if self.analysis_verbose:
                self.get_logger().info(json.dumps(analysis, ensure_ascii=False))

            if self._csv_writer is not None:
                row = {
                    "ts": frame.ts,
                    "source": frame.source,
                    "metrics_json": json.dumps(frame.metrics, ensure_ascii=False, sort_keys=True),
                    "command_linear_x": twist.linear.x,
                    "command_angular_z": twist.angular.z,
                    "speed_intent": self.last_intents.get("speed_intent", 0.5),
                    "steer_intent": self.last_intents.get("steer_intent", 0.5),
                }
                self._csv_writer.writerow(row)
                self._csv_flush_counter += 1
                if self._csv_flush_counter >= self._csv_flush_every_n:
                    self._csv_file.flush()
                    self._csv_flush_counter = 0

            if not self._calibrate:
                self.pub.publish(twist)

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

        # No frame this tick — the watchdog response is a pure decision.
        # Frames arrive at hop cadence (~2 Hz) but _tick runs at 20 Hz; the
        # inter-frame ticks are NOT loss, so both modes "replay" to keep the
        # partial at ~20 Hz. Only a real loss (stale) makes the node go
        # silent: single device sends one zero, dual device halts and lets
        # the fuser's freshness watchdog take over.
        action = decide_watchdog_action(
            stale=time.time() - self.last_msg_ts > self.watchdog_sec,
            connected=self._adapter_connected,
            stop_on_data_loss=self.stop_on_data_loss,
        )

        if action == "replay":
            # Within the grace window (both modes): hold the last intents.
            if not self._calibrate:
                self.pub.publish(self._intents_to_twist(self.last_intents))
            return

        # "zero" (single-device timeout) or "halt" (dual / already stopped):
        # the node publishes nothing further until data resumes.
        if self._adapter_connected:
            self._adapter_connected = False
            if action == "zero":
                self.pub.publish(Twist())  # one zero, then silent
            else:
                self.get_logger().warning("data loss — partial twist halted (dual mode)")
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

                w_pivot = speed * self.line_pivot_gain
                w_spin = speed * self.line_spin_gain
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
            if self._steer_role:
                # Steering role: turn in place, metric controls turn magnitude
                twist.linear.x = 0.0
                steer_mag = abs(steer_intent - 0.5)  # 0..0.25 (half-range mapping)
                if steer_mag >= self.steer_deadzone:
                    twist.angular.z = -self.steer_direction * self.turn_angular_speed * steer_mag
            else:
                twist.linear.x = self.max_forward_speed * speed_intent
                twist.angular.z = 0.0  # Speed role: no steering

        return twist

    def _update_leds(self) -> None:
        """Light circle LEDs to show current steer direction.

        Called on every tick so the first message after DDS discovery
        lands reliably — no priming counter or timing guess needed.

        Circle LED indices (from Thymio default behaviours source):
              0 (front)
          7       1
        6           2
          5       3
              4 (back)

        Right turn → LEDs 1, 2, 3 (right arc)
        Left turn  → LEDs 5, 6, 7 (left arc)
        No turn    → all off

        Only the steering node drives the LEDs — a speed node (including
        single-device mode) publishes nothing, otherwise two nodes contend
        on /led and overwrite each other.
        """
        if self._led_circle is None or not self._steer_role:
            return
        CIRCLE = 0  # thymio_msgs Led.CIRCLE
        if self.steer_direction > 0:
            values = [0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0]  # right arc
        elif self.steer_direction < 0:
            values = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0]  # left arc
        else:
            values = [0.0] * 8
        self._led_circle.publish(ThymioLed(id=CIRCLE, values=values))


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
