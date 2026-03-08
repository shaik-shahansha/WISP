"""
WISP I2C Scanner.

Auto-discovers sensors on the I2C bus at boot.
For each known address, instantiates the corresponding driver.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("wisp.scanner")

# Map of I2C address → (sensor_name, driver_class_path)
KNOWN_SENSORS: Dict[int, tuple[str, str]] = {
    0x76: ("bme280",   "wisp.hardware.sensors.bme280:BME280"),
    0x77: ("bme280",   "wisp.hardware.sensors.bme280:BME280"),
    0x44: ("sht31",    "wisp.hardware.sensors.sht31:SHT31"),
    0x45: ("sht31",    "wisp.hardware.sensors.sht31:SHT31"),
    0x23: ("bh1750",   "wisp.hardware.sensors.bh1750:BH1750"),
    0x5C: ("bh1750",   "wisp.hardware.sensors.bh1750:BH1750"),
    0x68: ("mpu6050",  "wisp.hardware.sensors.mpu6050:MPU6050"),
    0x69: ("mpu6050",  "wisp.hardware.sensors.mpu6050:MPU6050"),
    0x3C: ("ssd1306",  "wisp.hardware.sensors.ssd1306:SSD1306"),
    0x3D: ("ssd1306",  "wisp.hardware.sensors.ssd1306:SSD1306"),
}


class I2CScanner:
    """
    Scans the I2C bus and returns instantiated sensor driver objects.

    Parameters
    ----------
    sda, scl, freq : int, optional
        MicroPython I2C pin / frequency settings.
    bus : int
        Linux SMBus number (Raspberry Pi default: 1).
    """

    def __init__(
        self,
        sda: Optional[int] = None,
        scl: Optional[int] = None,
        freq: int = 400_000,
        bus: int = 1,
    ) -> None:
        self._sda = sda
        self._scl = scl
        self._freq = freq
        self._bus = bus
        self._i2c: Optional[Any] = None

    def scan(self) -> Dict[str, Any]:
        """
        Scan the I2C bus.

        Returns
        -------
        dict
            ``{sensor_name: driver_instance}`` for each detected sensor.
        """
        self._i2c = self._open_i2c()
        if self._i2c is None:
            logger.debug("No I2C bus available — skipping hardware discovery.")
            return {}

        found_addrs = self._scan_bus()
        logger.debug("I2C scan found addresses: %s", [f"0x{a:02X}" for a in found_addrs])

        discovered: Dict[str, Any] = {}
        seen_names: set[str] = set()

        for addr in found_addrs:
            if addr not in KNOWN_SENSORS:
                continue
            name, class_path = KNOWN_SENSORS[addr]
            if name in seen_names:
                continue  # only register first occurrence (e.g. BME280 at 0x76 + 0x77)
            driver = self._load_driver(class_path, addr)
            if driver is not None:
                discovered[name] = driver
                seen_names.add(name)
                logger.info("  Sensor found: %s @ 0x%02X", name, addr)

        return discovered

    # ------------------------------------------------------------------ #
    # Internals                                                           #
    # ------------------------------------------------------------------ #

    def _open_i2c(self) -> Optional[Any]:
        # MicroPython
        try:
            import machine  # type: ignore[import]
            if self._sda is not None and self._scl is not None:
                return machine.I2C(
                    1,
                    sda=machine.Pin(self._sda),
                    scl=machine.Pin(self._scl),
                    freq=self._freq,
                )
        except ImportError:
            pass

        # Raspberry Pi via smbus2
        try:
            import smbus2  # type: ignore[import]
            return smbus2.SMBus(self._bus)
        except (ImportError, FileNotFoundError, OSError):
            pass

        return None

    def _scan_bus(self) -> list[int]:
        try:
            # MicroPython
            if hasattr(self._i2c, "scan"):
                return self._i2c.scan()
            # smbus2
            found = []
            for addr in range(0x03, 0x78):
                try:
                    self._i2c.read_byte(addr)
                    found.append(addr)
                except Exception:
                    pass
            return found
        except Exception as exc:
            logger.debug("I2C scan failed: %s", exc)
            return []

    def _load_driver(self, class_path: str, addr: int) -> Optional[Any]:
        module_path, class_name = class_path.split(":")
        try:
            import importlib
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            return cls(i2c=self._i2c, addr=addr)
        except Exception as exc:
            logger.debug("Could not load driver %s: %s", class_path, exc)
            return None
