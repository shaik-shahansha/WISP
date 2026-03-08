"""
Basic WISP example — smart home sensor hub.

Runs on:
  - ESP32 / Pico W (MicroPython)
  - Raspberry Pi
  - Any Linux machine

How to run:
  wisp run            (Telegram transport, requires config.json)
  wisp simulate       (CLI transport, no Telegram needed)
"""

from wisp import WispDevice, capability


class SmartHome(WispDevice):
    device_name = "smart_home"
    description = "Home automation controller with temperature and humidity monitoring"

    @capability
    def read_temperature(self) -> dict:
        """Read the current ambient temperature."""
        sensor = self.hardware.sensor("bme280")
        if sensor:
            return {"temperature": sensor.temperature, "unit": "celsius"}
        return {"error": "BME280 sensor not found. Wire it to the I2C bus."}

    @capability
    def read_humidity(self) -> dict:
        """Read the current relative humidity."""
        sensor = self.hardware.sensor("bme280")
        if sensor:
            return {"humidity": sensor.humidity, "unit": "%"}
        return {"error": "BME280 sensor not found."}

    @capability
    def read_light(self) -> dict:
        """Read the ambient light level in lux."""
        sensor = self.hardware.sensor("bh1750")
        if sensor:
            return {"light": sensor.lux, "unit": "lux"}
        return {"error": "BH1750 sensor not found."}

    @capability(description="Turn the fan relay on or off")
    def set_fan(self, state: str) -> dict:
        """Control the fan relay."""
        on = state.lower() in ("on", "true", "1", "yes")
        self.hardware.set_output("fan", on)
        return {"fan": "on" if on else "off"}

    @capability(description="Turn the main light on or off")
    def set_light(self, state: str) -> dict:
        """Control the ceiling light relay."""
        on = state.lower() in ("on", "true", "1", "yes")
        self.hardware.set_output("light", on)
        return {"light": "on" if on else "off"}

    @capability
    def status(self) -> dict:
        """Report all sensor readings and output states at once."""
        result = {}
        for sensor_name in ("bme280", "bh1750"):
            sensor = self.hardware.sensor(sensor_name)
            if sensor:
                result.update(sensor.read())
        result.update(self.hardware.output_states())
        return result


if __name__ == "__main__":
    device = SmartHome.from_config("config.json")
    device.run()
