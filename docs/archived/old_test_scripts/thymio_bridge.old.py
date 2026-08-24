#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import asyncio

# Import only from top-level to avoid submodule path issues
from tdmclient import ClientAsync

class ThymioBridge(Node):
    def __init__(self):
        super().__init__('thymio_bridge')
        
        # 1. Minimal initialization without parameters to bypass version differences
        try:
            self.client = ClientAsync(tdm_addr="172.27.96.1", tdm_port=8596)
        except Exception as e:
            self.get_logger().error(f"Failed to initialize Client: {e}")
            return

        self.thymio_node = None
        
        # ROS 2 subscription
        self.subscription = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        
        self.get_logger().info('Thymio bridge started, preparing connection...')

    async def connect_loop(self):
        """Core connection logic"""
        self.get_logger().info('Searching for robots (please verify usbipd is connected and permissions are set)...')
        
        while rclpy.ok() and self.thymio_node is None:
            try:
                # Explicitly start local discovery (recommended practice in newer API)
                # Note: safe to ignore errors as some versions start this automatically in background
                try:
                    self.client.start_local_discovery()
                except:
                    pass

                # Try to get node
                # wait_for_node() returns when the first node is discovered
                self.thymio_node = await self.client.wait_for_node()
                await self.thymio_node.lock()
                
                self.get_logger().info(f'Robot locked successfully: {self.thymio_node.id_str}')
                break
            except Exception as e:
                # Keep trying until device is discovered
                await asyncio.sleep(2.0)

    async def cmd_vel_callback(self, msg):
        if self.thymio_node is None:
            return

        # Speed conversion: ROS (m/s) -> Thymio (-500 to 500)
        # 0.1 m/s roughly corresponds to 300-400 Thymio units
        v = msg.linear.x * 400.0  
        w = msg.angular.z * 200.0 
        
        l_speed = int(v - w)
        r_speed = int(v + w)

        # Clamp range
        l_speed = max(min(l_speed, 500), -500)
        r_speed = max(min(r_speed, 500), -500)

        try:
            # Use dict parameters
            await self.thymio_node.set_variables({
                "motor.left.target": [l_speed],
                "motor.right.target": [r_speed]
            })
        except Exception as e:
            self.get_logger().warn(f"Failed to send command: {e}")

async def main():
    rclpy.init()
    node = ThymioBridge()
    
    # Start background async connection task
    conn_task = asyncio.create_task(node.connect_loop())
    
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.01)
            await asyncio.sleep(0.01)
    except KeyboardInterrupt:
        node.get_logger().info('Stop signal detected, stopping robot...')
    finally:
        # --- Critical stop logic ---
        if node.thymio_node:
            try:
                # 1. Force send 0 speed
                await node.thymio_node.set_variables({
                    "motor.left.target": [0],
                    "motor.right.target": [0]
                })
                # 2. Wait briefly to ensure command is sent
                await asyncio.sleep(0.2)
                # 3. Unlock robot
                await node.thymio_node.unlock()
                node.get_logger().info('Robot stopped and unlocked safely.')
            except Exception as e:
                node.get_logger().error(f"Cleanup failed: {e}")
        
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
