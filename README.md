# WISP

### The natural language remote control framework for physical devices.

**Give any device a voice — ESP32, Raspberry Pi, ROS2 robots, and more.**

[![PyPI version](https://img.shields.io/pypi/v/wisp-ai.svg?color=blue&logo=pypi&label=wisp-ai)](https://pypi.org/project/wisp-ai/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![MicroPython](https://img.shields.io/badge/MicroPython-1.21%2B-orange)](https://micropython.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

```
You: "turn on the fan and tell me the temperature"
   ↓  natural language
WISP: 🌡 temperature: 24.3°C  ✅ fan: ON
   ↑  real hardware action
```

> **"Your chip. Your robot. Your AI. No server needed."**

---

## What is WISP?

WISP is a Python framework that lets you control **physical hardware** with natural language.
You describe what your device can do with plain Python methods.
WISP handles talking to the AI, translating what users say into real hardware actions, and sending the reply back — all without a server, MQTT broker, or cloud middleware.

```
[Your Phone]
     │
  Telegram  (or HTTP webhook, or CLI)
     │
[Your Device — ESP32 / Pi / ROS2 Robot]
     │── @capability methods defined by you
     │── AI (Groq / OpenRouter) via HTTPS — grounded in real capabilities
     │── AI returns JSON command
     └── WISP executes on real pins / topics → sends reply
```

**The core idea:** the AI only ever sees the capabilities *you* define.
It cannot hallucinate a LiDAR that isn't there.

---

## Install

```bash
pip install wisp-ai
```

Zero mandatory dependencies — uses Python stdlib only.
Optional extras for Raspberry Pi GPIO:
```bash
pip install "wisp-ai[rpi]"   # adds smbus2 + RPi.GPIO
```

---

## 30-second quickstart

**1. Scaffold a new project**

```bash
wisp new my_device
cd my_device
```

**2. Edit `config.json`** — add your free tokens:

```json
{
  "telegram": { "token": "YOUR_BOT_TOKEN" },
  "ai":       { "provider": "groq", "api_key": "YOUR_GROQ_API_KEY" }
}
```

> Get a Telegram token free from [@BotFather](https://t.me/botfather).
> Get a Groq key free (no credit card) at [console.groq.com](https://console.groq.com).

**3. Run**

```bash
wisp run          # real Telegram bot
wisp simulate     # test locally, no Telegram needed
```

**That's it.**

---

## The framework API

WISP is built around one idea: subclass `WispDevice`, decorate methods with `@capability`.

```python
from wisp import WispDevice, capability


class SmartHome(WispDevice):
    device_name = "smart_home"
    description  = "Home automation controller"

    @capability
    def read_temperature(self) -> dict:
        """Read the current ambient temperature."""
        sensor = self.hardware.sensor("bme280")  # auto-discovered at boot
        return {"temperature": sensor.temperature, "unit": "celsius"}

    @capability
    def set_fan(self, state: str) -> dict:
        """Turn the fan relay on or off."""
        self.hardware.set_output("fan", state == "on")
        return {"fan": state}

    @capability
    def status(self) -> dict:
        """Report all sensor readings and relay states at once."""
        result = {}
        for cap in self.capabilities.all():
            if cap.name.startswith("read_"):
                result.update(cap(self))
        result.update(self.hardware.output_states())
        return result


if __name__ == "__main__":
    device = SmartHome.from_config("config.json")
    device.run()
```

**Conversation:**

```
You:  what is the temperature?
WISP: 🌡 temperature: 24.30
      unit: celsius

You:  turn on the fan
WISP: ✅ fan: on

You:  take a photo
WISP: ❌ No camera capability. I have: read_temperature, set_fan, status

You:  show me everything
WISP: 🌡 temperature: 24.30
      💧 humidity: 62.10
      📊 pressure: 1013.40
      ✅ fan: on
      ✅ light: off
```

---

## Platforms

| Platform | How to run | Auto-discovers |
|----------|------------|----------------|
| **ESP32** | MicroPython 1.21+ via `mpremote` | I2C sensors, GPIO |
| **Pi Pico W** | MicroPython 1.21+ | I2C sensors, GPIO |
| **Raspberry Pi** | `pip install wisp-ai[rpi]` | I2C via smbus2, BCM GPIO |
| **ROS2 Robot** | `pip install wisp-ai` + `rclpy` | Live ROS2 topic graph |
| **Any Linux** | `pip install wisp-ai` | Mock hardware, custom capabilities |
| **Desktop** | `pip install wisp-ai` | `wisp simulate` for testing |

---

## Auto-discovered sensors

Wire, boot, done — no code changes:

| Sensor  | Reads | I2C Address |
|---------|-------|-------------|
| BME280  | temperature, humidity, pressure | 0x76, 0x77 |
| SHT31   | temperature, humidity | 0x44, 0x45 |
| BH1750  | light (lux) | 0x23, 0x5C |
| MPU6050 | accelerometer, gyroscope, temp | 0x68, 0x69 |
| SSD1306 | OLED display status | 0x3C, 0x3D |

---

## Transports

| Transport | Usage | Use case |
|-----------|-------|----------|
| `telegram` | `device.run()` | Production — any phone |
| `cli` | `device.run(transport="cli")` or `wisp simulate` | Local testing |
| `http` | `device.run(transport="http")` | Webhooks, n8n, Make |

---

## ROS2 Robot

Add one line to give any ROS2 robot natural language control:

```python
from wisp import WispDevice, capability
from wisp.plugins.ros2 import ROS2Plugin

class MyRobot(WispDevice):
    device_name = "turtlebot"
    description  = "TurtleBot3 running ROS2 Humble"

    @capability
    def status(self) -> dict:
        """Report robot status."""
        return {"robot": self.name, "status": "online"}

if __name__ == "__main__":
    device = MyRobot.from_config("config.json")
    device.use(ROS2Plugin())   # ← scans live ROS2 graph, adds movement/nav/sensors
    device.run()
```

```
You:  go forward slowly for 3 seconds
WISP: ✅ direction: forward  speed: 0.3  duration: 3.0  status: done

You:  navigate to x=3 y=1.5
WISP: ✅ x: 3.0  y: 1.5  yaw: 0.0  status: goal sent

You:  what's in front of me?
WISP: 📡 min_distance: 0.42  max_distance: 4.87  avg_distance: 2.31  points: 512

You:  play music
WISP: ❌ No play_music capability. I have: movement, navigation, read_lidar, read_battery
```

---

## Plugins

Plugins extend a device without subclassing:

```python
from wisp.plugins.base import WispPlugin
from wisp.core.capability import CapabilitySpec


class WeatherPlugin(WispPlugin):
    """Pulls live weather from an external API."""

    def attach(self, device):
        spec = CapabilitySpec(
            name="read_weather",
            description="Get current weather from OpenMeteo API",
            fn=self._read_weather,
        )
        device.add_capability(spec)

    def _read_weather(self, device):
        import urllib.request, json
        url = "https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.1&current=temperature_2m"
        with urllib.request.urlopen(url) as r:
            data = json.loads(r.read())
        return {"temperature": data["current"]["temperature_2m"], "unit": "C"}


device = MyDevice.from_config("config.json")
device.use(WeatherPlugin())
device.run()
```

---

## AI providers

| Provider | Free tier | Recommended model |
|----------|-----------|-------------------|
| **Groq** | ~14,400 req/day, no credit card | `llama-3.3-70b-versatile` |
| **OpenRouter** | 200 req/day on free models | `meta-llama/llama-3.3-70b-instruct:free` |

Switch by editing one line in `config.json`:

```json
"ai": {
  "provider": "openrouter",
  "api_key":  "sk-or-...",
  "model":    "meta-llama/llama-3.3-70b-instruct:free"
}
```

---

## Lifecycle hooks

Override any of these in your `WispDevice` subclass:

```python
class MyDevice(WispDevice):

    def on_boot(self) -> None:
        """Called once after hardware is ready, before transport starts."""
        print("Device booted!")

    def on_message(self, user: str, text: str):
        """Called before AI processing. Return a string to short-circuit AI."""
        if text.lower() == "ping":
            return "pong"   # skip AI entirely
        return None         # proceed normally

    def on_reply(self, user: str, reply: str) -> str:
        """Modify or log the reply before it is sent."""
        return f"[{self.name}] {reply}"

    def on_error(self, exc: Exception) -> str:
        """Customise the error message sent to the user."""
        return f"💥 Something went wrong: {exc}"
```

---

## CLI

```
wisp new my_device            # scaffold project (templates: basic, sensors, ros2)
wisp run                      # run main.py with Telegram transport
wisp run --transport cli      # run in interactive CLI mode
wisp simulate                 # shortcut for --transport cli
wisp check                    # validate config.json
wisp version                  # print version
```

---

## For microcontrollers (ESP32 / Pico W)

This `wisp` package targets **CPython 3.9+** and runs on any Linux-capable device
(Raspberry Pi, NVIDIA Jetson, x86 SBC, etc.).

For bare-metal microcontrollers (ESP32, Pi Pico W) a **separate MicroPython port**
lives in the [`wisp/device/`](../wisp/) directory. It shares the same high-level
concepts (AI ↔ capabilities ↔ hardware) but is a distinct, stripped-down codebase
that avoids CPython-only features (`dataclasses`, `typing`, `enum`).

```bash
# Flash the MicroPython port to your board
pip install mpremote
mpremote connect auto cp -r wisp/device/. :
```

> **Platform summary**
> | Runtime | Target | Package |
> |---------|--------|---------|
> | CPython 3.9+ | Raspberry Pi, Linux SBC, Desktop | `pip install wisp-ai` |
> | MicroPython 1.21+ | ESP32, Pi Pico W | copy `wisp/device/` via mpremote |

---

## Project structure

```
framework/
├── wisp/                      # pip-installable package
│   ├── core/
│   │   ├── device.py          # WispDevice base class + metaclass
│   │   ├── capability.py      # @capability decorator + CapabilityRegistry
│   │   ├── config.py          # WispConfig — JSON + env loading
│   │   └── errors.py          # Custom exceptions
│   ├── ai/
│   │   ├── client.py          # Unified AI client (Groq / OpenRouter)
│   │   ├── prompt.py          # Grounded system prompt builder
│   │   └── providers/
│   │       ├── groq.py
│   │       └── openrouter.py
│   ├── transports/
│   │   ├── telegram.py        # Telegram long-poll (no external deps)
│   │   ├── cli.py             # Interactive terminal REPL
│   │   └── http.py            # HTTP webhook (stdlib http.server)
│   ├── hardware/
│   │   ├── hal.py             # Hardware abstraction layer
│   │   ├── scanner.py         # I2C auto-discovery
│   │   └── sensors/           # BME280, BH1750, SHT31, MPU6050, SSD1306
│   ├── plugins/
│   │   ├── base.py            # WispPlugin ABC
│   │   └── ros2.py            # ROS2 graph scanner + executor
│   └── cli/
│       └── main.py            # wisp CLI entry point
├── examples/
│   ├── smart_home/            # Temperature + relay control
│   ├── weather_station/       # Custom capabilities, no hardware needed
│   └── ros2_robot/            # TurtleBot3 / Husky / any ROS2 robot
├── tests/
│   ├── test_core.py
│   └── test_ai.py
├── pyproject.toml             # pip install wisp-ai
└── CHANGELOG.md
```

---

## Testing

```bash
cd framework
pip install -e ".[dev]"
pytest
```

Test without hardware using the weather station example:
```bash
export WISP_TELEGRAM_TOKEN=your_token
export WISP_AI_API_KEY=your_key
wisp simulate --script examples/weather_station/main.py
```

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Add tests in `tests/`
4. Run `ruff check wisp/` and `pytest`
5. Open a pull request

---

## License

MIT — use freely in personal and commercial projects.

---

**Built with the philosophy: the AI should only ever claim what the hardware can actually do.**

[PyPI](https://pypi.org/project/wisp-ai/) · [GitHub](https://github.com/shaik-shahansha/wisp) · [Changelog](CHANGELOG.md)
