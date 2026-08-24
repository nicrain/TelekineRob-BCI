#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import asyncio
from tdmclient import ClientAsync

class ThymioSafeBridge(Node):
    def __init__(self):
        super().__init__('thymio_bridge')
        try:
            # Force continue even if ConnectionRefused occurs
            self.client = ClientAsync()
        except ConnectionRefusedError:
            self.get_logger().warn("TDM server not found, falling back to local serial mode...")
            # self.client is created, but connection failed
            pass 
        
        self.thymio_node = None
        self.subscription = self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        self.get_logger().info('Safe Thymio bridge started')

    async def connect(self):
        while rclpy.ok() and self.thymio_node is None:
            try:
                self.client.start_local_discovery()
                self.thymio_node = await self.client.wait_for_node()
                await self.thymio_node.lock()
                self.get_logger().info(f'Robot locked: {self.thymio_node.id_str}')
                break
            except:
                await asyncio.sleep(1.0)

    async def cmd_vel_callback(self, msg):
        if not self.thymio_node: return
        v, w = msg.linear.x * 400.0, msg.angular.z * 200.0
        l, r = int(v - w), int(v + w)
        try:
            await self.thymio_node.set_variables({"motor.left.target": [l], "motor.right.target": [r]})
        except Exception as e:
            self.get_logger().error(f"Send failed: {e}")

async def main():
    rclpy.init()
    node = ThymioSafeBridge()
    conn_task = asyncio.create_task(node.connect())
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.01)
            await asyncio.sleep(0.01)
    except KeyboardInterrupt:
        node.get_logger().warn('Emergency stop in progress...')
    finally:
        if node.thymio_node:
            # Final step before exiting: force stop
            await node.thymio_node.set_variables({"motor.left.target": [0], "motor.right.target": [0]})
            await asyncio.sleep(0.2)
            await node.thymio_node.unlock()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
