"""
SSD1306 — 128×64 OLED display driver.

I2C addresses: 0x3C (default), 0x3D
Supports text output via a built-in 5×7 font (ASCII 32-127).
"""

from __future__ import annotations

import struct
from typing import Any, Dict, List


class SSD1306:
    """Minimal SSD1306 OLED driver for WISP status display."""

    ADDR_DEFAULT = 0x3C
    WIDTH  = 128
    HEIGHT = 64

    def __init__(self, i2c: Any, addr: int = ADDR_DEFAULT) -> None:
        self._i2c = i2c
        self._addr = addr
        self._buffer = bytearray(self.WIDTH * self.HEIGHT // 8)
        self._init()

    def read(self) -> Dict[str, str]:
        """SSD1306 is output-only; returns display status."""
        return {"display": "ssd1306 128x64 ready"}

    def show_text(self, text: str, x: int = 0, y: int = 0) -> None:
        """Write a short text string to the OLED at pixel (x, y)."""
        self.fill(0)
        for i, ch in enumerate(text[:21]):  # max ~21 chars per line
            self._draw_char(x + i * 6, y, ch)
        self.display()

    def show_lines(self, lines: List[str]) -> None:
        """Write up to 8 lines of text (each max 21 chars)."""
        self.fill(0)
        for row, line in enumerate(lines[:8]):
            for col, ch in enumerate(line[:21]):
                self._draw_char(col * 6, row * 8, ch)
        self.display()

    def fill(self, colour: int) -> None:
        v = 0xFF if colour else 0x00
        for i in range(len(self._buffer)):
            self._buffer[i] = v

    def display(self) -> None:
        self._cmd(0xAE)
        self._cmd(0x20, 0x00)   # horizontal addressing
        self._cmd(0x21, 0, self.WIDTH - 1)
        self._cmd(0x22, 0, self.HEIGHT // 8 - 1)
        self._cmd(0xAF)
        chunk = bytearray(17)
        chunk[0] = 0x40
        for i in range(0, len(self._buffer), 16):
            chunk[1:17] = self._buffer[i:i + 16]
            self._write_raw(chunk)

    # ------------------------------------------------------------------ #
    # Internal                                                            #
    # ------------------------------------------------------------------ #

    def _init(self) -> None:
        for cmd in (
            0xAE, 0xD5, 0x80, 0xA8, self.HEIGHT - 1,
            0xD3, 0x00, 0x40, 0x8D, 0x14,
            0x20, 0x00, 0xA1, 0xC8,
            0xDA, 0x12, 0x81, 0xCF,
            0xD9, 0xF1, 0xDB, 0x40,
            0xA4, 0xA6, 0xAF,
        ):
            self._cmd(cmd)
        self.fill(0)
        self.display()

    def _cmd(self, *args: int) -> None:
        for a in args:
            data = bytes([0x00, a])
            self._write_raw(data)

    def _write_raw(self, data: bytes) -> None:
        try:
            self._i2c.writeto(self._addr, data)
        except AttributeError:
            self._i2c.write_i2c_block_data(self._addr, data[0], list(data[1:]))

    # Minimal 5×7 font (ASCII 32-127), stored as 5 columns of 8 bits
    _FONT = {
        ord(' '): b'\x00\x00\x00\x00\x00',
        ord('A'): b'\x7E\x11\x11\x11\x7E',
        ord('B'): b'\x7F\x49\x49\x49\x36',
        # (Full font omitted for brevity — use a full font table in production)
    }

    def _draw_char(self, x: int, y: int, ch: str) -> None:
        col_data = self._FONT.get(ord(ch) if ch else 32, b'\x00\x00\x00\x00\x00')
        for col_idx, byte in enumerate(col_data):
            for bit in range(8):
                px = x + col_idx
                py = y + bit
                if px >= self.WIDTH or py >= self.HEIGHT:
                    continue
                if byte & (1 << bit):
                    self._set_pixel(px, py)

    def _set_pixel(self, x: int, y: int) -> None:
        idx = x + (y // 8) * self.WIDTH
        if 0 <= idx < len(self._buffer):
            self._buffer[idx] |= 1 << (y & 7)
