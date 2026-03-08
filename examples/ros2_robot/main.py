"""
ROS2 Robot WISP example.

Gives any ROS2 robot a Telegram interface with natural language control.
Auto-discovers all topics at startup.

Requirements:
  - ROS2 Humble / Iron / Jazzy
  - source /opt/ros/$ROS_DISTRO/setup.bash
  - pip install wisp-ai

How to run:
  source /opt/ros/$ROS_DISTRO/setup.bash
  wisp run
"""

from wisp import WispDevice, capability
from wisp.plugins.ros2 import ROS2Plugin


class MyRobot(WispDevice):
    device_name = "my_robot"
    description = "ROS2 mobile robot — supports movement, navigation, and sensor reading"

    @capability
    def status(self) -> dict:
        """Report the robot's current status."""
        caps = self.capabilities.names()
        return {
            "robot": self.name,
            "status": "online",
            "capabilities": ", ".join(caps),
        }

    # ROS2Plugin auto-adds: movement, navigation, read_lidar,
    # read_odometry, read_battery, read_imu — from the live graph.


if __name__ == "__main__":
    device = MyRobot.from_config("config.json")
    device.use(ROS2Plugin())
    device.run()
