#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from tdmclient import ClientAsync
import socket
import json
import asyncio
import time
import os  # Import os at the top of the file
from threading import Thread

class ThymioGazeSystem(Node):
    def __init__(self):
        super().__init__('thymio_gaze_system')
        self.thymio_node = None
        self.last_msg_time = time.time()
        
        # Initialize connection
        self.client = ClientAsync(tdm_addr="172.27.96.1", tdm_port=8596)

        # UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 5005))
        self.sock.setblocking(False)

        # Timer: receive every 0.1s, balance real-time responsiveness and buffer load
        self.create_timer(0.1, self.udp_receive_loop) 
        self.create_timer(0.2, self.watchdog_check)

        self.get_logger().info("Real-time system: optimized responsiveness and emergency stop")

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
                self.process_gaze(float(val['x']), float(val['y']))
            except:
                pass

    def process_gaze(self, x, y):
        self.last_msg_time = time.time()
        twist = Twist()
        
        # 1. Highest priority: look down (y > 0.8) -> backward
        if y > 0.8:
            twist.linear.x = -0.15  # Negative value means backward
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

        if self.thymio_node:
            # Use async dispatch
            asyncio.run_coroutine_threadsafe(self.send_to_robot(twist), self.loop)

    def watchdog_check(self):
        if time.time() - self.last_msg_time > 0.5:
            if self.thymio_node:
                asyncio.run_coroutine_threadsafe(self.send_to_robot(Twist()), self.loop)

    async def send_to_robot(self, twist):
        v, w = twist.linear.x * 400.0, twist.angular.z * 200.0
        l, r = int(v - w), int(v + w)
        l, r = max(min(l, 500), -500), max(min(r, 500), -500)
        try:
            await self.thymio_node.set_variables({"motor.left.target": [l], "motor.right.target": [r]})
        except:
            pass

    async def connect_robot(self):
        self.get_logger().info('Recherche du Thymio en cours...')
        try:
            self.thymio_node = await self.client.wait_for_node()
            await self.thymio_node.lock()
            self.get_logger().info(f'Robot verrouillé : {self.thymio_node.id_str}')
        except Exception as e:
            self.get_logger().error(f"Échec de la connexion : {e}")

async def run_async_tasks(node):
    await node.connect_robot()
    while rclpy.ok():
        await asyncio.sleep(0.1)


def main():
    rclpy.init()
    node = ThymioGazeSystem()
    
    node.loop = asyncio.new_event_loop()
    def start_background_loop(loop):
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_async_tasks(node))
        except:
            pass

    thread = Thread(target=start_background_loop, args=(node.loop,), daemon=True)
    thread.start()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\nSignal d'arrêt détecté, fermeture en cours...")
    finally:
        print("Exécution de l'arrêt d'urgence matériel...")
        if node.thymio_node:
            try:
                # Use temporary event loop to send stop command
                async def final_stop():
                    # Obtain control and clear commands
                    await node.thymio_node.lock()
                    await node.thymio_node.set_variables({
                        "motor.left.target": [0], 
                        "motor.right.target": [0]
                    })
                    await asyncio.sleep(0.3)
                    await node.thymio_node.unlock()
                
                stop_loop = asyncio.new_event_loop()
                stop_loop.run_until_complete(final_stop())
                stop_loop.close()
                print("Hardware command sent.")
            except Exception as e:
                print(f"Failed to send stop command: {e}")

        # Clean up and exit
        print("Closing program...")
        try:
            node.destroy_node()
            rclpy.shutdown()
        except:
            pass
        # Force exit to terminate process
        os._exit(0)

if __name__ == '__main__':
    main()