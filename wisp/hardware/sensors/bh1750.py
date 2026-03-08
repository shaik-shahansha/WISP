"""
BH1750 — ambient light sensor driver.

I2C addresses: 0x23 (default), 0x5C
Output: light level in lux (0.96–65535 lux).
"""

from __future__ import annotations

import time
from typing import Any, Dict


class BH1750:
    """BH1750 ambient light sensor driver."""

    ADDR_DEFAULT = 0x23

    _CMD_POWER_ON     = 0x01
    _CMD_RESET        = 0x07
    _CMD_CONT_H_RES   = 0x10   # Continuous high-res mode (1 lux resolution)

    def __init__(self, i2c: Any, addr: int = ADDR_DEFAULT) -> None:
        self._i2c = i2c
        self._addr = addr
        self._init()

    def _init(self) -> None:
        self._write(self._CMD_POWER_ON)
        self._write(self._CMD_RESET)
        self._write(self._CMD_CONT_H_RES)
        time.sleep(0.18)  # max measurement time for high-res mode

    @property
    def lux(self) -> float:
        return self._read_lux()

    def read(self) -> Dict[str, float]:
        return {"light": round(self._read_lux(), 1)}

    def _read_lux(self) -> float:
        data = self._read(2)
        raw = (data[0] << 8) | data[1]
        return raw / 1.2  # conversion factor per datasheet

    def _write(self, cmd: int) -> None:
        try:
            self._i2c.writeto(self._addr, bytes([cmd]))
        except AttributeError:
            self._i2c.write_byte(self._addr, cmd)

    def _read(self, n: int) -> bytes:
        try:
            return self._i2c.readfrom(self._addr, n)
        except AttributeError:
            return bytes(self._i2c.read_i2c_block_data(self._addr, 0x00, n))
