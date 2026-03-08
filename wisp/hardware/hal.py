"""
WISP Hardware Abstraction Layer (HAL).

Wraps machine.I2C / machine.Pin (MicroPython) and
smbus2 / RPi.GPIO (Raspberry Pi / Linux) behind a single interface.
On desktop / CI, uses mock implementations so code runs without hardware.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from wisp.core.config import HardwareConfig
from wisp.core.errors import HardwareError

logger = logging.getLogger("wisp.hardware")


class HardwareLayer:
    """
    Platform-agnostic hardware layer.

    Detects the current platform and initialises the appropriate drivers.
    Exposes a uniform API used by sensor drivers and the executor.
    """

    def __init__(self, config: HardwareConfig) -> None:
        self._config = config
        self._i2c: Optional[Any] = None
        self._gpio: Dict[str, Any] = {}
        self._platform = _detect_platform()

    def boot(self) -> None:
        """Initialise I2C bus and GPIO based on detected platform."""
        logger.info("Hardware platform: %s", self._platform)
        if self._platform == "micropython":
            self._init_micropython()
        elif self._platform == "raspberry_pi":
            self._init_raspberry_pi()
        else:
            logger.debug("Running on desktop — hardware calls will use mock drivers.")

    # ------------------------------------------------------------------ #
    # I2C                                                                 #
    # ------------------------------------------------------------------ #

    @property
    def i2c(self) -> Any:
        """Return the I2C bus object (platform-specific)."""
        if self._i2c is None:
            self._init_i2c()
        return self._i2c

    def i2c_read(self, addr: int, n: int) -> bytes:
        try:
            if self._platform == "micropython":
                return self._i2c.readfrom(addr, n)
            elif self._platform == "raspberry_pi":
                return bytes(self._i2c.read_i2c_block_data(addr, 0, n))
            else:
                return bytes(n)  # mock
        except Exception as exc:
            raise HardwareError(f"I2C read from 0x{addr:02X} failed: {exc}") from exc

    def i2c_write(self, addr: int, data: bytes) -> None:
        try:
            if self._platform == "micropython":
                self._i2c.writeto(addr, data)
            elif self._platform == "raspberry_pi":
                self._i2c.write_i2c_block_data(addr, data[0], list(data[1:]))
            # mock: no-op
        except Exception as exc:
            raise HardwareError(f"I2C write to 0x{addr:02X} failed: {exc}") from exc

    def i2c_read_register(self, addr: int, register: int, n: int) -> bytes:
        try:
            if self._platform == "micropython":
                self._i2c.writeto(addr, bytes([register]))
                return self._i2c.readfrom(addr, n)
            elif self._platform == "raspberry_pi":
                return bytes(self._i2c.read_i2c_block_data(addr, register, n))
            else:
                return bytes(n)  # mock
        except Exception as exc:
            raise HardwareError(
                f"I2C read register 0x{register:02X} from 0x{addr:02X} failed: {exc}"
            ) from exc

    def i2c_scan(self) -> list[int]:
        """Return list of I2C addresses that responded."""
        try:
            if self._platform == "micropython":
                return self._i2c.scan()
            elif self._platform == "raspberry_pi":
                found = []
                for addr in range(0x03, 0x78):
                    try:
                        self._i2c.read_byte(addr)
                        found.append(addr)
                    except Exception:
                        pass
                return found
            else:
                return []
        except Exception as exc:
            raise HardwareError(f"I2C scan failed: {exc}") from exc

    # ------------------------------------------------------------------ #
    # GPIO                                                                #
    # ------------------------------------------------------------------ #

    def set_output(self, name: str, value: bool) -> None:
        """Set a named GPIO output high (True) or low (False)."""
        pin_num = self._config.gpio_outputs.get(name)
        if pin_num is None:
            raise HardwareError(f"Unknown GPIO output '{name}'")
        self._set_pin(pin_num, value)

    def get_output(self, name: str) -> bool:
        """Get the current value of a named GPIO output."""
        if self._platform == "desktop":
            return self._gpio.get(name, False)
        pin_num = self._config.gpio_outputs.get(name)
        if pin_num is None:
            raise HardwareError(f"Unknown GPIO output '{name}'")
        return self._get_pin(pin_num)

    def output_states(self) -> Dict[str, bool]:
        """Return current state of all configured outputs."""
        return {name: self.get_output(name) for name in self._config.gpio_outputs}

    # ------------------------------------------------------------------ #
    # Platform init                                                       #
    # ------------------------------------------------------------------ #

    def _init_micropython(self) -> None:
        try:
            import machine  # type: ignore[import]
            sda = self._config.i2c_sda
            scl = self._config.i2c_scl
            if sda is not None and scl is not None:
                self._i2c = machine.I2C(
                    1,
                    sda=machine.Pin(sda),
                    scl=machine.Pin(scl),
                    freq=self._config.i2c_freq,
                )
        except ImportError:
            pass

    def _init_raspberry_pi(self) -> None:
        try:
            import smbus2  # type: ignore[import]
            self._i2c = smbus2.SMBus(self._config.i2c_bus)
        except ImportError:
            logger.warning("smbus2 not installed. Run: pip install smbus2")
        try:
            import RPi.GPIO as GPIO  # type: ignore[import]
            GPIO.setmode(GPIO.BCM)
            for name, pin in self._config.gpio_outputs.items():
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
                self._gpio[name] = (GPIO, pin)
        except ImportError:
            logger.warning("RPi.GPIO not installed. Run: pip install RPi.GPIO")

    def _init_i2c(self) -> None:
        if self._platform == "raspberry_pi":
            self._init_raspberry_pi()
        elif self._platform == "micropython":
            self._init_micropython()

    def _set_pin(self, pin_num: int, value: bool) -> None:
        if self._platform == "micropython":
            import machine  # type: ignore[import]
            machine.Pin(pin_num, machine.Pin.OUT).value(int(value))
        elif self._platform == "raspberry_pi":
            try:
                import RPi.GPIO as GPIO  # type: ignore[import]
                GPIO.output(pin_num, GPIO.HIGH if value else GPIO.LOW)
            except ImportError:
                pass
        # desktop: just track state
        for name, p in self._config.gpio_outputs.items():
            if p == pin_num:
                self._gpio[name] = value

    def _get_pin(self, pin_num: int) -> bool:
        if self._platform == "micropython":
            import machine  # type: ignore[import]
            return bool(machine.Pin(pin_num, machine.Pin.OUT).value())
        elif self._platform == "raspberry_pi":
            try:
                import RPi.GPIO as GPIO  # type: ignore[import]
                return bool(GPIO.input(pin_num))
            except ImportError:
                pass
        for name, p in self._config.gpio_outputs.items():
            if p == pin_num:
                return bool(self._gpio.get(name, False))
        return False

    def sensor(self, name: str) -> Any:
        """Return a named sensor from the scanner (set after auto-discovery)."""
        return self._sensors.get(name) if hasattr(self, "_sensors") else None


# ------------------------------------------------------------------ #
# Platform detection                                                  #
# ------------------------------------------------------------------ #

def _detect_platform() -> str:
    try:
        import sys
        if sys.implementation.name == "micropython":
            return "micropython"
    except AttributeError:
        pass

    try:
        import os
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo") as f:
                info = f.read()
            if "Raspberry Pi" in info or "BCM" in info:
                return "raspberry_pi"
    except Exception:
        pass

    return "desktop"
