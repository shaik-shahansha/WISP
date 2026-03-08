"""
WISP configuration loader.

Loads and validates a config.json (or config.yaml) file.
Provides typed access to all configuration sections.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from wisp.core.errors import ConfigurationError


@dataclass
class WiFiConfig:
    ssid: str = ""
    password: str = ""


@dataclass
class TelegramConfig:
    token: str = ""
    allowed_users: List[int] = field(default_factory=list)


@dataclass
class AIConfig:
    provider: str = "groq"                         # groq | openrouter
    api_key: str = ""
    model: str = "llama-3.3-70b-versatile"
    max_tokens: int = 1024
    temperature: float = 0.1


@dataclass
class HardwareConfig:
    """I2C / GPIO hardware config."""

    # MicroPython / Pi Pico / ESP32
    i2c_sda: Optional[int] = None                  # GPIO SDA pin
    i2c_scl: Optional[int] = None                  # GPIO SCL pin
    i2c_freq: int = 400_000

    # Raspberry Pi
    i2c_bus: int = 1                               # Linux /dev/i2c-*

    gpio_outputs: Dict[str, int] = field(default_factory=dict)  # name -> BCM pin


@dataclass
class WispConfig:
    """Root configuration object."""

    device_name: str = "wisp_device"
    wifi: WiFiConfig = field(default_factory=WiFiConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)

    # raw dict kept for custom / extra keys
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------ #
    # Loaders                                                             #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_file(cls, path: str | Path) -> "WispConfig":
        """Load config from a JSON file."""
        path = Path(path)
        if not path.exists():
            raise ConfigurationError(f"Config file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(f"Invalid JSON in {path}: {exc}") from exc
        return cls._from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WispConfig":
        return cls._from_dict(data)

    @classmethod
    def from_env(cls) -> "WispConfig":
        """Load config from environment variables (useful for cloud deployments)."""
        data: Dict[str, Any] = {
            "device_name": os.environ.get("WISP_DEVICE_NAME", "wisp_device"),
            "telegram": {"token": os.environ.get("WISP_TELEGRAM_TOKEN", "")},
            "ai": {
                "provider": os.environ.get("WISP_AI_PROVIDER", "groq"),
                "api_key": os.environ.get("WISP_AI_API_KEY", os.environ.get("GROQ_API_KEY", "")),
                "model": os.environ.get("WISP_AI_MODEL", "llama-3.3-70b-versatile"),
            },
        }
        return cls._from_dict(data)

    # ------------------------------------------------------------------ #
    # Internal                                                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "WispConfig":
        wifi_data = data.get("wifi", {})
        tg_data = data.get("telegram", {})
        ai_data = data.get("ai", {})
        hw_data = data.get("hardware", {})

        wifi = WiFiConfig(
            ssid=wifi_data.get("ssid", ""),
            password=wifi_data.get("password", ""),
        )

        telegram = TelegramConfig(
            token=tg_data.get("token", ""),
            allowed_users=tg_data.get("allowed_users", []),
        )

        ai = AIConfig(
            provider=ai_data.get("provider", "groq"),
            api_key=ai_data.get("api_key", ""),
            model=ai_data.get("model", "llama-3.3-70b-versatile"),
            max_tokens=int(ai_data.get("max_tokens", 1024)),
            temperature=float(ai_data.get("temperature", 0.1)),
        )

        gpio_outputs = hw_data.get("gpio_outputs", {})
        hardware = HardwareConfig(
            i2c_sda=hw_data.get("i2c_sda"),
            i2c_scl=hw_data.get("i2c_scl"),
            i2c_freq=int(hw_data.get("i2c_freq", 400_000)),
            i2c_bus=int(hw_data.get("i2c_bus", 1)),
            gpio_outputs=gpio_outputs,
        )

        return cls(
            device_name=data.get("device_name", "wisp_device"),
            wifi=wifi,
            telegram=telegram,
            ai=ai,
            hardware=hardware,
            _raw=data,
        )

    def validate(self) -> None:
        """Raise ConfigurationError if required fields are missing."""
        if not self.telegram.token:
            raise ConfigurationError(
                "telegram.token is required. "
                "Get a free token from @BotFather on Telegram."
            )
        if not self.ai.api_key:
            raise ConfigurationError(
                "ai.api_key is required. "
                "Get a free key from https://console.groq.com or https://openrouter.ai/keys"
            )

    def dump(self) -> Dict[str, Any]:
        """Return a sanitised dict (no secrets) for logging."""
        return {
            "device_name": self.device_name,
            "ai": {"provider": self.ai.provider, "model": self.ai.model},
            "telegram": {"token": "***"},
            "hardware": {
                "i2c_bus": self.hardware.i2c_bus,
                "gpio_outputs": list(self.hardware.gpio_outputs.keys()),
            },
        }
