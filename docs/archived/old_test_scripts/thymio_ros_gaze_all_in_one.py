#!/usr/bin/env python3
"""WSL/ROS2 version "All-in-one" Thymio control (without tdm/Thymio Suite dependency).

This script:
- Runs as a ROS2 node
- Receives gaze point data (x, y) from local UDP port 5005
- Publishes /cmd_vel velocity commands to Thymio based on gaze direction

Prerequisites:
1. ROS2 environment sourced (source /opt/ros/<distro>/setup.bash or workspace install/setup.bash)
2. Thymio connected via asebaros + thymio_driver (see README)
3. Gaze data sent to UDP port 5005 in JSON format: {"x": 0.5, "y": 0.4}

Usage:
  python3 thymio_ros_gaze_all_in_one.py
"""

import json
import socket
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class ThymioRosGaze(Node):
    def __init__(self):
        super().__init__('thymio_ros_gaze_all_in_one')
        self.last_msg_time = time.time()

        # ROS topics
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # UDP receiver settings
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', 5005))
        self.sock.setblocking(False)

        # Timers
        self.create_timer(0.1, self.udp_receive_loop)
        self.create_timer(0.2, self.watchdog_check)

        self.get_logger().info('ROS gaze control node started, waiting for UDP gaze data (port 5005)')

    def udp_receive_loop(self):
        latest_data = None
        while True:
            try:
                data, addr = self.sock.recvfrom(1024)
                latest_data = data
            except (BlockingIOError, socket.error):
                break

        if latest_data:
            try:
                val = json.loads(latest_data.decode())
                self.process_gaze(float(val.get('x', 0.5)), float(val.get('y', 0.5)))
            except Exception:
                pass

    def process_gaze(self, x, y):
        self.last_msg_time = time.time()
        twist = Twist()

        # 1. Highest priority: look down (y > 0.8) -> backward
        if y > 0.8:
            twist.linear.x = -0.15
            twist.angular.z = 0.0

        # 2. Next check left/right: x < 0.3 is turn left
        elif x < 0.3:
            twist.linear.x = 0.1
            twist.angular.z = 1.2

        # 3. x > 0.7 is turn right
        elif x > 0.7:
            twist.linear.x = 0.1
            twist.angular.z = -1.2

        # 4. Other cases (look middle or up): straight
        else:
            twist.linear.x = 0.2
            twist.angular.z = 0.0

        self.cmd_vel_pub.publish(twist)

    def watchdog_check(self):
        if time.time() - self.last_msg_time > 0.5:
            self.cmd_vel_pub.publish(Twist())


def main():
    rclpy.init()
    node = ThymioRosGaze()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
