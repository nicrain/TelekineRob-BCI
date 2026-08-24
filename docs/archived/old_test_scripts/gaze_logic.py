import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point, Twist
import time

class GazeLogicSafe(Node):
    def __init__(self):
        super().__init__('gaze_logic')
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)
        self.subscription = self.create_subscription(Point, '/gaze_data', self.callback, 10)
        self.last_msg_time = time.time()
        # Timer: check if data is stale every 0.1s
        self.create_timer(0.1, self.watchdog_check)

    def callback(self, msg):
        self.last_msg_time = time.time() # Refresh timestamp
        twist = Twist()
        # Control logic
        if msg.x < 0.3: twist.angular.z = 0.8; twist.linear.x = 0.05
        elif msg.x > 0.7: twist.angular.z = -0.8; twist.linear.x = 0.05
        else: twist.linear.x = 0.1
        self.publisher_.publish(twist)

    def watchdog_check(self):
        # If no gaze data received for > 0.5s, judge as loss of control and send stop command
        if time.time() - self.last_msg_time > 0.5:
            stop_msg = Twist()
            self.publisher_.publish(stop_msg)
            # self.get_logger().warn("⚠️ Gaze signal lost, auto brake")

def main():
    rclpy.init(); rclpy.spin(GazeLogicSafe()); rclpy.shutdown()

if __name__ == '__main__':
    main()
