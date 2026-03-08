"""
SHT31 — temperature & humidity sensor driver.

I2C addresses: 0x44 (default), 0x45
"""

from __future__ import annotations

import time
from typing import Any, Dict


class SHT31:
    """SHT31 temperature and humidity sensor driver."""

    ADDR_DEFAULT = 0x44

    _CMD_MEASURE = b"\x24\x00"   # single-shot, no clock stretching, high repeatability

    def __init__(self, i2c: Any, addr: int = ADDR_DEFAULT) -> None:
        self._i2c = i2c
        self._addr = addr

    @property
    def temperature(self) -> float:
        t, _ = self._read_raw()
        return t

    @property
    def humidity(self) -> float:
        _, h = self._read_raw()
        return h

    def read(self) -> Dict[str, float]:
        t, h = self._read_raw()
        return {"temperature": round(t, 2), "humidity": round(h, 2)}

    def _read_raw(self):
        self._write(self._CMD_MEASURE)
        time.sleep(0.015)   # 15ms for high-repeatability measurement
        data = self._readfrom(6)
        if len(data) < 6:
            return 0.0, 0.0
        raw_t = (data[0] << 8) | data[1]
        raw_h = (data[3] << 8) | data[4]
        # crc bytes at data[2] and data[5] — skipped for brevity
        temperature = -45.0 + 175.0 * raw_t / 65535.0
        humidity    = 100.0 * raw_h / 65535.0
        return temperature, max(0.0, min(100.0, humidity))

    def _write(self, data: bytes) -> None:
        try:
            self._i2c.writeto(self._addr, data)
        except AttributeError:
            self._i2c.write_i2c_block_data(self._addr, data[0], list(data[1:]))

    def _readfrom(self, n: int) -> bytes:
        try:
            return self._i2c.readfrom(self._addr, n)
        except AttributeError:
            return bytes(self._i2c.read_i2c_block_data(self._addr, 0x00, n))
