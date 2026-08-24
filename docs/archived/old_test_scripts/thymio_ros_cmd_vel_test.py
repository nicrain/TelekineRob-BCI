#!/usr/bin/env python3
"""ROS2 script: control Thymio via /cmd_vel (without Thymio Suite dependency).

Prerequisites:
- ROS2 is installed and sourced in the current environment.
- Thymio ROS nodes (e.g. asebaros + thymio_driver) are running in the same ROS_DOMAIN / ROS_NAMESPACE.
- Thymio is connected (USB via usbipd or network mode), and proxied as a ROS node by asebaros.

Workflow:
  1) Move forward for 2 seconds
  2) Stop for 2 seconds
  3) Exit

Usage:
  python3 thymio_ros_cmd_vel_test.py
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class ThymioCmdVelTest(Node):
    def __init__(self):
        super().__init__('thymio_ros_cmd_vel_test')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.start_time = self.get_clock().now()
        self.get_logger().info('Publishing /cmd_vel to Thymio: 2s forward, 2s stop, then exit.')
        self.timer = self.create_timer(0.1, self.timer_callback)

    def timer_callback(self):
        elapsed = (self.get_clock().now() - self.start_time).nanoseconds * 1e-9
        twist = Twist()

        if elapsed < 2.0:
            twist.linear.x = 0.12
        elif elapsed < 4.0:
            twist.linear.x = 0.0
        else:
            self.get_logger().info('Test completed, exiting.')
            try:
                rclpy.shutdown()
            except RuntimeError:
                pass
            return

        self.pub.publish(twist)


def main():
    rclpy.init()
    node = ThymioCmdVelTest()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
