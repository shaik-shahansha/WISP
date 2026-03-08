"""
MPU6050 — 6-axis accelerometer + gyroscope + temperature sensor.

I2C addresses: 0x68 (default, AD0 low), 0x69 (AD0 high)
"""

from __future__ import annotations

import struct
from typing import Any, Dict


class MPU6050:
    """MPU6050 IMU driver — reads accel, gyro, and die temperature."""

    ADDR_DEFAULT = 0x68

    _REG_PWR_MGMT_1  = 0x6B
    _REG_ACCEL_XOUT  = 0x3B
    _REG_GYRO_XOUT   = 0x43
    _REG_TEMP_OUT    = 0x41
    _REG_WHO_AM_I    = 0x75

    _ACCEL_SCALE = 16384.0  # ±2g default
    _GYRO_SCALE  = 131.0    # ±250°/s default

    def __init__(self, i2c: Any, addr: int = ADDR_DEFAULT) -> None:
        self._i2c = i2c
        self._addr = addr
        self._init()

    def _init(self) -> None:
        # Wake up (clear sleep bit)
        self._write_reg(self._REG_PWR_MGMT_1, 0x00)

    @property
    def acceleration(self) -> Dict[str, float]:
        raw = self._read_reg(self._REG_ACCEL_XOUT, 6)
        ax, ay, az = struct.unpack(">hhh", raw)
        return {
            "accel_x": round(ax / self._ACCEL_SCALE, 4),
            "accel_y": round(ay / self._ACCEL_SCALE, 4),
            "accel_z": round(az / self._ACCEL_SCALE, 4),
        }

    @property
    def gyro(self) -> Dict[str, float]:
        raw = self._read_reg(self._REG_GYRO_XOUT, 6)
        gx, gy, gz = struct.unpack(">hhh", raw)
        return {
            "gyro_x": round(gx / self._GYRO_SCALE, 4),
            "gyro_y": round(gy / self._GYRO_SCALE, 4),
            "gyro_z": round(gz / self._GYRO_SCALE, 4),
        }

    @property
    def temperature(self) -> float:
        raw = self._read_reg(self._REG_TEMP_OUT, 2)
        raw_t, = struct.unpack(">h", raw)
        return round(raw_t / 340.0 + 36.53, 2)

    def read(self) -> Dict[str, Any]:
        result = {}
        result.update(self.acceleration)
        result.update(self.gyro)
        result["temperature"] = self.temperature
        return result

    def _write_reg(self, reg: int, value: int) -> None:
        try:
            self._i2c.writeto_mem(self._addr, reg, bytes([value]))
        except AttributeError:
            self._i2c.write_i2c_block_data(self._addr, reg, [value])

    def _read_reg(self, reg: int, n: int) -> bytes:
        try:
            return self._i2c.readfrom_mem(self._addr, reg, n)
        except AttributeError:
            return bytes(self._i2c.read_i2c_block_data(self._addr, reg, n))
