#!/usr/bin/env python3
"""Fuse partial Twist commands from two EEG nodes into a single /cmd_vel.

Dual-device topology::

    eeg_control_node (role=speed)     --/eeg_cmd_vel/speed    --> cmd_vel_fuser
    eeg_control_node_eeg2 (role=steer)--/eeg_cmd_vel/steering --> cmd_vel_fuser
    cmd_vel_fuser --/cmd_vel--> Thymio  (linear.x<-speed, angular.z<-steering)

The merge helpers are duck-typed (any object exposing ``.linear.x`` /
``.angular.z``) and importable without ROS, so they are unit-testable on a
machine with no ROS installation. The rclpy node itself is built lazily in
``main()``.
"""

import time
from typing import Optional


def merge_twists(speed, steer):
    """Return a twist whose linear.x comes from *speed* and angular.z from
    *steer*; every other component is zero."""
    out = type(speed)()
    out.linear.x = float(speed.linear.x)
    out.angular.z = float(steer.angular.z)
    return out


def build_command(speed, steer, speed_ok: bool, steer_ok: bool):
    """Any missing/stale input → zero velocity; otherwise fuse the pair.

    Returns ``None`` only when neither input has ever arrived (the caller
    substitutes its pre-built zero twist in that case); a stale input still
    yields a zero twist via ``type(speed)()`` / ``type(steer)()``.
    """
    if not (speed_ok and steer_ok):
        if speed is None and steer is None:
            return None
        ref = speed if speed is not None else steer
        return type(ref)()
    return merge_twists(speed, steer)


def main(args: Optional[list] = None) -> None:
    import rclpy
    from geometry_msgs.msg import Twist
    from rclpy.node import Node

    class CmdVelFuser(Node):
        """Subscribes to both partial twists and re-emits the fused one.

        Pure data plane — no policy computation. Freshness (not "a zero
        message arrived") decides fail-safe: any input older than
        ``watchdog_sec`` → whole robot zero velocity. This distinguishes a
        disconnected device from a relaxed user.
        """

        def __init__(self) -> None:
            super().__init__("cmd_vel_fuser")
            self.declare_parameter("speed_topic", "/eeg_cmd_vel/speed")
            self.declare_parameter("steer_topic", "/eeg_cmd_vel/steering")
            self.declare_parameter("cmd_topic", "/cmd_vel")
            self.declare_parameter("publish_hz", 20.0)
            self.declare_parameter("watchdog_sec", 0.5)
            self.declare_parameter("verbose", False)

            self._speed: Optional[Twist] = None
            self._steer: Optional[Twist] = None
            self._speed_ts = 0.0
            self._steer_ts = 0.0
            self._stopped = True        # whether currently holding zero velocity
            self._zero_twist = Twist()
            self._start = time.time()
            self._warned_no_data = False

            self._watchdog_sec = float(self.get_parameter("watchdog_sec").value)
            self._verbose = bool(self.get_parameter("verbose").value)

            self.create_subscription(
                Twist, str(self.get_parameter("speed_topic").value), self._on_speed, 10
            )
            self.create_subscription(
                Twist, str(self.get_parameter("steer_topic").value), self._on_steer, 10
            )
            self._pub = self.create_publisher(
                Twist, str(self.get_parameter("cmd_topic").value), 10
            )
            hz = float(self.get_parameter("publish_hz").value)
            self.create_timer(1.0 / max(hz, 1e-6), self._tick)

        def _on_speed(self, msg: Twist) -> None:
            self._speed, self._speed_ts = msg, time.time()

        def _on_steer(self, msg: Twist) -> None:
            self._steer, self._steer_ts = msg, time.time()

        def _tick(self) -> None:
            now = time.time()
            speed_ok = (
                self._speed is not None and now - self._speed_ts <= self._watchdog_sec
            )
            steer_ok = (
                self._steer is not None and now - self._steer_ts <= self._watchdog_sec
            )
            twist = build_command(self._speed, self._steer, speed_ok, steer_ok)
            if twist is None:
                twist = self._zero_twist

            stopped = twist.linear.x == 0.0 and twist.angular.z == 0.0
            if stopped and not self._stopped:
                self.get_logger().warning(
                    "fuser: zero velocity — input missing/stale (speed_ok=%s steer_ok=%s)",
                    speed_ok, steer_ok,
                )
            elif not stopped and self._stopped:
                self.get_logger().info("fuser: resumed fused control")
            self._stopped = stopped

            if not self._warned_no_data and self._speed is None and self._steer is None:
                if now - self._start > 5.0:
                    self.get_logger().warning(
                        "fuser: no partial-twist input yet — holding zero velocity"
                    )
                    self._warned_no_data = True

            self._pub.publish(twist)
            if self._verbose:
                self.get_logger().info(
                    "fused linear.x=%.3f angular.z=%.3f (speed_ok=%s steer_ok=%s)",
                    twist.linear.x, twist.angular.z, speed_ok, steer_ok,
                )

    rclpy.init(args=args)
    node = CmdVelFuser()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
