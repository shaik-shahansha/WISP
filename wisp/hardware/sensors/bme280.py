"""
BME280 — temperature, humidity, pressure sensor driver.

I2C addresses: 0x76 (default), 0x77
Compatible with Bosch BME280 and BMP280.
"""

from __future__ import annotations

import struct
from typing import Any, Dict


class BME280:
    """
    Lightweight BME280 / BMP280 driver.

    Reads temperature, humidity, and pressure via I2C.
    Works on MicroPython (machine.I2C) and Linux (smbus2).
    """

    ADDR_DEFAULT = 0x76

    _REG_CHIP_ID   = 0xD0
    _REG_RESET     = 0xE0
    _REG_CTRL_HUM  = 0xF2
    _REG_STATUS    = 0xF3
    _REG_CTRL_MEAS = 0xF4
    _REG_CONFIG    = 0xF5
    _REG_DATA      = 0xF7
    _CALIB1        = 0x88
    _CALIB2        = 0xE1

    def __init__(self, i2c: Any, addr: int = ADDR_DEFAULT) -> None:
        self._i2c = i2c
        self._addr = addr
        self._calib: Dict[str, Any] = {}
        self._init()

    def _init(self) -> None:
        self._write(_BME280_REG_CTRL_HUM := 0xF2, b"\x01")
        self._write(0xF4, b"\x27")   # osrs_t=001, osrs_p=001, mode=11 (normal)
        self._write(0xF5, b"\xA0")   # t_sb=101 (1000ms), filter=000
        self._read_calibration()

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    @property
    def temperature(self) -> float:
        t, _, _ = self._read_raw()
        return t

    @property
    def humidity(self) -> float:
        _, h, _ = self._read_raw()
        return h

    @property
    def pressure(self) -> float:
        _, _, p = self._read_raw()
        return p

    def read(self) -> Dict[str, float]:
        t, h, p = self._read_raw()
        result = {"temperature": round(t, 2)}
        if h is not None:
            result["humidity"] = round(h, 2)
        if p is not None:
            result["pressure"] = round(p, 2)
        return result

    # ------------------------------------------------------------------ #
    # Internal                                                            #
    # ------------------------------------------------------------------ #

    def _read_raw(self):
        data = self._read_reg(0xF7, 8)
        adc_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        adc_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        adc_h = (data[6] << 8) | data[7] if len(data) >= 8 else 0

        c = self._calib
        # Temperature
        var1 = (adc_t / 16384.0 - c["T1"] / 1024.0) * c["T2"]
        var2 = (adc_t / 131072.0 - c["T1"] / 8192.0) ** 2 * c["T3"]
        t_fine = var1 + var2
        temperature = t_fine / 5120.0

        # Humidity
        humidity = None
        if "H1" in c:
            x = t_fine - 76800.0
            if x != 0:
                x = (adc_h - (c["H4"] * 64.0 + c["H5"] / 16384.0 * x)) * (
                    c["H2"] / 65536.0 * (1.0 + c["H6"] / 67108864.0 * x * (1.0 + c["H3"] / 67108864.0 * x))
                )
                x = x * (1.0 - c["H1"] * x / 524288.0)
                humidity = max(0.0, min(100.0, x))

        # Pressure
        pressure = None
        var1 = t_fine / 2.0 - 64000.0
        var2 = var1 * var1 * c["P6"] / 32768.0
        var2 = var2 + var1 * c["P5"] * 2.0
        var2 = var2 / 4.0 + c["P4"] * 65536.0
        var1 = (c["P3"] * var1 * var1 / 524288.0 + c["P2"] * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * c["P1"]
        if var1 != 0:
            p_raw = 1048576.0 - adc_p
            p_raw = ((p_raw - var2 / 4096.0) * 6250.0) / var1
            var1 = c["P9"] * p_raw * p_raw / 2147483648.0
            var2 = p_raw * c["P8"] / 32768.0
            pressure = (p_raw + (var1 + var2 + c["P7"]) / 16.0) / 100.0

        return temperature, humidity, pressure

    def _read_calibration(self) -> None:
        d = self._read_reg(0x88, 24)
        c: Dict[str, Any] = {}
        c["T1"] = (d[1] << 8) | d[0]
        c["T2"] = _signed16((d[3] << 8) | d[2])
        c["T3"] = _signed16((d[5] << 8) | d[4])
        for i, k in enumerate(["P1","P2","P3","P4","P5","P6","P7","P8","P9"], start=6):
            raw = (d[i * 2 - 6 + 7] << 8) | d[i * 2 - 6 + 6]
            c[k] = raw if k == "P1" else _signed16(raw)
        try:
            h0 = self._read_reg(0xA1, 1)
            c["H1"] = h0[0]
            h = self._read_reg(0xE1, 7)
            c["H2"] = _signed16((h[1] << 8) | h[0])
            c["H3"] = h[2]
            c["H4"] = _signed16((h[3] << 4) | (h[4] & 0x0F))
            c["H5"] = _signed16((h[5] << 4) | (h[4] >> 4))
            c["H6"] = _signed8(h[6])
        except Exception:
            pass
        self._calib = c

    def _write(self, reg: int, data: bytes) -> None:
        try:
            self._i2c.writeto_mem(self._addr, reg, data)
        except AttributeError:
            self._i2c.write_i2c_block_data(self._addr, reg, list(data))

    def _read_reg(self, reg: int, n: int) -> bytes:
        try:
            return self._i2c.readfrom_mem(self._addr, reg, n)
        except AttributeError:
            return bytes(self._i2c.read_i2c_block_data(self._addr, reg, n))


def _signed16(v: int) -> int:
    return v - 65536 if v >= 32768 else v


def _signed8(v: int) -> int:
    return v - 256 if v >= 128 else v
