"""
WISP ROS2 Plugin.

Scans the live ROS2 graph at startup and registers
discovered topics as capabilities on the device.

Usage::

    from wisp import WispDevice
    from wisp.plugins.ros2 import ROS2Plugin

    class MyRobot(WispDevice):
        description = "TurtleBot3 running ROS2 Humble"

    device = MyRobot.from_config("config.json")
    device.use(ROS2Plugin())
    device.run(transport="telegram")
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from wisp.core.device import WispDevice

logger = logging.getLogger("wisp.plugins.ros2")

# Map of known ROS2 topic patterns → (capability_name, description)
TOPIC_MAP: List[Tuple[str, str, str]] = [
    ("/cmd_vel",               "movement",   "Move the robot: go forward, backward, turn, or stop"),
    ("/navigate_to_pose",      "navigation", "Navigate to x/y coordinates using Nav2"),
    ("/scan",                  "lidar",      "Read LiDAR obstacle distances"),
    ("/odom",                  "odometry",   "Read robot position and velocity"),
    ("/battery_state",         "battery",    "Read battery level and voltage"),
    ("/imu/data",              "imu",        "Read accelerometer and gyroscope"),
    ("/camera/image_raw",      "camera",     "Camera is present"),
    ("/joint_states",          "joints",     "Read robot joint positions"),
    ("/map",                   "map",        "Occupancy map is available"),
    ("/tf",                    "tf",         "Coordinate frame transforms available"),
]


class ROS2Plugin:
    """
    WISP plugin that integrates a ROS2 robot.

    Call ``device.use(ROS2Plugin())`` before ``device.run()``.
    """

    def __init__(
        self,
        node_name: str = "wisp_node",
        cmd_vel_topic: str = "/cmd_vel",
        nav_topic: str = "/navigate_to_pose",
    ) -> None:
        self._node_name = node_name
        self._cmd_vel_topic = cmd_vel_topic
        self._nav_topic = nav_topic
        self._node: Optional[Any] = None
        self._executor: Optional[Any] = None
        self._spin_thread: Optional[threading.Thread] = None

    def attach(self, device: "WispDevice") -> None:
        """Called by device.use() — scans ROS2 graph and registers capabilities."""
        import rclpy  # type: ignore[import]

        if not rclpy.ok():
            rclpy.init()

        from rclpy.node import Node  # type: ignore[import]

        self._node = Node(self._node_name)

        # Spin in background thread
        self._executor = rclpy.get_global_executor()
        self._spin_thread = threading.Thread(target=self._spin, daemon=True)
        self._spin_thread.start()

        # Scan graph
        discovered = self._scan_graph()

        # Register capabilities on the device
        for topic, cap_name, cap_desc in discovered:
            self._register_capability(device, topic, cap_name, cap_desc)
            logger.info("  ROS2 capability: %-16s <- %s", cap_name, topic)

        logger.info("ROS2 plugin ready (%d capabilities)", len(discovered))

    # ------------------------------------------------------------------ #
    # Graph scanning                                                      #
    # ------------------------------------------------------------------ #

    def _scan_graph(self) -> List[Tuple[str, str, str]]:
        time.sleep(1.0)  # wait for graph to be populated
        try:
            topics = dict(self._node.get_topic_names_and_types())
        except Exception as exc:
            logger.warning("Could not scan ROS2 graph: %s", exc)
            return []

        found = []
        for topic_pattern, cap_name, cap_desc in TOPIC_MAP:
            if topic_pattern in topics:
                found.append((topic_pattern, cap_name, cap_desc))
        return found

    # ------------------------------------------------------------------ #
    # Capability registration                                             #
    # ------------------------------------------------------------------ #

    def _register_capability(
        self,
        device: "WispDevice",
        topic: str,
        cap_name: str,
        cap_desc: str,
    ) -> None:
        from wisp.core.capability import CapabilitySpec, CapabilityParam

        node = self._node

        if cap_name == "movement":
            spec = self._make_movement_spec(node)
        elif cap_name == "navigation":
            spec = self._make_navigation_spec(node)
        elif cap_name == "lidar":
            spec = self._make_subscriber_spec(node, topic, cap_name, cap_desc, "sensor_msgs/LaserScan", _parse_lidar)
        elif cap_name == "odometry":
            spec = self._make_subscriber_spec(node, topic, cap_name, cap_desc, "nav_msgs/Odometry", _parse_odom)
        elif cap_name == "battery":
            spec = self._make_subscriber_spec(node, topic, cap_name, cap_desc, "sensor_msgs/BatteryState", _parse_battery)
        elif cap_name == "imu":
            spec = self._make_subscriber_spec(node, topic, cap_name, cap_desc, "sensor_msgs/Imu", _parse_imu)
        else:
            spec = CapabilitySpec(name=cap_name, description=cap_desc, fn=lambda self_dev: {"status": f"{cap_name} present"})

        device.add_capability(spec)

    def _make_movement_spec(self, node: Any) -> "CapabilitySpec":
        from wisp.core.capability import CapabilitySpec, CapabilityParam

        def move(self_dev: Any, direction: str = "forward", speed: float = 0.3, duration: float = 2.0) -> Dict[str, Any]:
            try:
                from geometry_msgs.msg import Twist  # type: ignore[import]
                import rclpy  # type: ignore[import]
                pub = node.create_publisher(Twist, self_dev._ros2_cmd_vel_topic if hasattr(self_dev, "_ros2_cmd_vel_topic") else "/cmd_vel", 10)
                twist = Twist()
                d = direction.lower()
                if d in ("forward", "f"):
                    twist.linear.x = float(speed)
                elif d in ("backward", "back", "b"):
                    twist.linear.x = -float(speed)
                elif d in ("left", "l"):
                    twist.angular.z = float(speed)
                elif d in ("right", "r"):
                    twist.angular.z = -float(speed)
                elif d in ("stop", "s"):
                    pass
                pub.publish(twist)
                time.sleep(float(duration))
                stop = Twist()
                pub.publish(stop)
                return {"direction": direction, "speed": speed, "duration": duration, "status": "done"}
            except Exception as exc:
                return {"error": str(exc)}

        return CapabilitySpec(
            name="movement",
            description="Move the robot: direction (forward/backward/left/right/stop), speed (m/s), duration (s)",
            fn=move,
            parameters=[
                CapabilityParam("direction", "str", "forward, backward, left, right, or stop"),
                CapabilityParam("speed", "float", "Speed in m/s", required=False, default=0.3),
                CapabilityParam("duration", "float", "Duration in seconds", required=False, default=2.0),
            ],
        )

    def _make_navigation_spec(self, node: Any) -> "CapabilitySpec":
        from wisp.core.capability import CapabilitySpec, CapabilityParam

        def navigate(self_dev: Any, x: float, y: float, yaw: float = 0.0) -> Dict[str, Any]:
            try:
                from geometry_msgs.msg import PoseStamped  # type: ignore[import]
                from std_msgs.msg import Header  # type: ignore[import]
                import math
                pub = node.create_publisher(PoseStamped, "/navigate_to_pose/goal", 10)
                msg = PoseStamped()
                msg.header.frame_id = "map"
                msg.pose.position.x = float(x)
                msg.pose.position.y = float(y)
                msg.pose.orientation.z = math.sin(float(yaw) / 2)
                msg.pose.orientation.w = math.cos(float(yaw) / 2)
                pub.publish(msg)
                return {"x": x, "y": y, "yaw": yaw, "status": "goal sent"}
            except Exception as exc:
                return {"error": str(exc)}

        return CapabilitySpec(
            name="navigation",
            description="Navigate to x/y coordinates via Nav2",
            fn=navigate,
            parameters=[
                CapabilityParam("x", "float", "Target X coordinate"),
                CapabilityParam("y", "float", "Target Y coordinate"),
                CapabilityParam("yaw", "float", "Target heading in radians", required=False, default=0.0),
            ],
        )

    def _make_subscriber_spec(
        self,
        node: Any,
        topic: str,
        cap_name: str,
        cap_desc: str,
        msg_type_str: str,
        parser,
    ) -> "CapabilitySpec":
        from wisp.core.capability import CapabilitySpec

        cache: Dict[str, Any] = {}

        def subscribe_once(self_dev: Any, _cache=cache, _topic=topic, _parser=parser) -> Dict[str, Any]:
            if not _cache:
                # Wait for one message
                try:
                    mod_name, cls_name = msg_type_str.replace("/", ".").rsplit(".", 1)
                    import importlib
                    mod = importlib.import_module(mod_name.replace("/", "."))
                    MsgClass = getattr(mod, cls_name)

                    received = []

                    def cb(msg, _r=received):
                        if not _r:
                            _r.append(msg)

                    sub = node.create_subscription(MsgClass, _topic, cb, 1)
                    deadline = time.time() + 3.0
                    while not received and time.time() < deadline:
                        time.sleep(0.05)
                    node.destroy_subscription(sub)

                    if received:
                        _cache.update(_parser(received[0]))
                except Exception as exc:
                    return {"error": f"Could not read {cap_name}: {exc}"}

            return dict(_cache)

        return CapabilitySpec(
            name=f"read_{cap_name}",
            description=cap_desc,
            fn=subscribe_once,
        )

    def _spin(self) -> None:
        try:
            import rclpy  # type: ignore[import]
            rclpy.spin(self._node)
        except Exception:
            pass


# ------------------------------------------------------------------ #
# Message parsers                                                     #
# ------------------------------------------------------------------ #

def _parse_lidar(msg: Any) -> Dict[str, Any]:
    ranges = [r for r in msg.ranges if r > 0 and r < 100]
    if not ranges:
        return {"lidar": "no data"}
    return {
        "min_distance": round(min(ranges), 3),
        "max_distance": round(max(ranges), 3),
        "avg_distance": round(sum(ranges) / len(ranges), 3),
        "points": len(ranges),
    }


def _parse_odom(msg: Any) -> Dict[str, Any]:
    p = msg.pose.pose.position
    v = msg.twist.twist.linear
    return {
        "x": round(p.x, 3),
        "y": round(p.y, 3),
        "z": round(p.z, 3),
        "linear_vel": round(v.x, 3),
    }


def _parse_battery(msg: Any) -> Dict[str, Any]:
    return {
        "battery_percent": round(msg.percentage * 100, 1),
        "voltage": round(msg.voltage, 2),
    }


def _parse_imu(msg: Any) -> Dict[str, Any]:
    a = msg.linear_acceleration
    g = msg.angular_velocity
    return {
        "accel_x": round(a.x, 3),
        "accel_y": round(a.y, 3),
        "accel_z": round(a.z, 3),
        "gyro_z": round(g.z, 3),
    }
