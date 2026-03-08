"""
Custom capabilities example.

Shows how to build a device with fully custom capabilities —
no auto-discovery, pure Python, works without any hardware.

Perfect for:
  - Mock testing
  - Cloud-connected devices
  - Custom APIs

Run: wisp simulate --script main.py
"""

import random
from wisp import WispDevice, capability


class WeatherStation(WispDevice):
    device_name = "weather_station"
    description = "Outdoor weather station with temperature, humidity, wind, and rain sensors"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._relay_states = {"heater": False, "fan": False}

    @capability
    def read_temperature(self) -> dict:
        """Read outdoor temperature."""
        # In production: read from a real sensor
        temp = round(random.uniform(18.0, 32.0), 1)
        return {"temperature": temp, "unit": "C", "location": "outdoor"}

    @capability
    def read_humidity(self) -> dict:
        """Read outdoor relative humidity."""
        humidity = round(random.uniform(40.0, 90.0), 1)
        return {"humidity": humidity, "unit": "%"}

    @capability
    def read_wind(self) -> dict:
        """Read wind speed and direction."""
        speed = round(random.uniform(0.0, 15.0), 1)
        direction = random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
        return {"wind_speed": speed, "wind_direction": direction, "unit": "m/s"}

    @capability
    def read_rain(self) -> dict:
        """Check if it is raining and how much."""
        raining = random.random() < 0.3
        rainfall = round(random.uniform(0, 5.0), 2) if raining else 0.0
        return {"raining": raining, "rainfall_mm": rainfall}

    @capability
    def read_all(self) -> dict:
        """Read all weather sensors at once."""
        result = {}
        result.update(self.read_temperature())
        result.update(self.read_humidity())
        result.update(self.read_wind())
        result.update(self.read_rain())
        return result

    @capability(description="Turn the heater on or off based on temperature")
    def set_heater(self, state: str) -> dict:
        """Control the greenhouse heater relay."""
        on = state.lower() in ("on", "yes", "true", "1")
        self._relay_states["heater"] = on
        return {"heater": "on" if on else "off"}

    @capability(description="Turn the ventilation fan on or off")
    def set_fan(self, state: str) -> dict:
        """Control the ventilation fan relay."""
        on = state.lower() in ("on", "yes", "true", "1")
        self._relay_states["fan"] = on
        return {"fan": "on" if on else "off"}

    @capability
    def relay_status(self) -> dict:
        """Report current state of all relays."""
        return {k: "on" if v else "off" for k, v in self._relay_states.items()}


if __name__ == "__main__":
    # No real hardware needed — runs anywhere Python runs
    from wisp.core.config import WispConfig
    from wisp.core.config import TelegramConfig, AIConfig
    import os

    config = WispConfig.from_env()  # reads WISP_TELEGRAM_TOKEN and WISP_AI_API_KEY

    device = WeatherStation(config=config)
    device.run(transport="cli")  # or "telegram" in production
