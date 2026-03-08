"""
WISP — Wireless Intelligence for Sensing & Physical-control
Natural language remote control for physical devices.

The framework to give any device a voice.

    from wisp import WispDevice, capability

    class MyDevice(WispDevice):

        @capability
        def read_temperature(self):
            \"\"\"Read the current temperature.\"\"\"
            return {"temperature": 24.3, "unit": "C"}

    device = MyDevice.from_config("config.json")
    device.run()
"""

from wisp.core.device import WispDevice
from wisp.core.capability import capability
from wisp.core.config import WispConfig
from wisp.core.errors import (
    WispError,
    ConfigurationError,
    HardwareError,
    AIError,
    TransportError,
    CapabilityError,
)
from wisp.hardware.scanner import I2CScanner
from wisp.hardware.hal import HardwareLayer

__version__ = "0.1.0"
__author__ = "WISP Contributors"
__license__ = "MIT"

__all__ = [
    # Core
    "WispDevice",
    "capability",
    "WispConfig",
    # Hardware
    "I2CScanner",
    "HardwareLayer",
    # Errors
    "WispError",
    "ConfigurationError",
    "HardwareError",
    "AIError",
    "TransportError",
    "CapabilityError",
    # Meta
    "__version__",
]
