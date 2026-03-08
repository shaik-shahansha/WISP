"""
WISP CLI — wisp new | wisp run | wisp simulate | wisp check

Entry point registered as ``wisp`` in pyproject.toml.
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from pathlib import Path


# ------------------------------------------------------------------ #
# Entry point                                                         #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wisp",
        description="WISP — Natural language remote control for devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Commands:
              new <name>       Scaffold a new WISP device project
              run [main.py]    Run a WISP device (default: main.py)
              simulate         Start an interactive CLI simulator
              check            Validate config.json
              version          Print version

            Examples:
              wisp new my_sensor_hub
              wisp run
              wisp simulate --config config.json
              wisp check
        """),
    )
    sub = parser.add_subparsers(dest="command")

    # new
    p_new = sub.add_parser("new", help="Scaffold a new WISP project")
    p_new.add_argument("name", help='Project name (e.g. "my_robot")')
    p_new.add_argument(
        "--template",
        default="basic",
        choices=["basic", "sensors", "ros2"],
        help="Project template",
    )

    # run
    p_run = sub.add_parser("run", help="Run a WISP device")
    p_run.add_argument("script", nargs="?", default="main.py", help="Script to run")
    p_run.add_argument("--transport", default="telegram", choices=["telegram", "cli", "http"])

    # simulate
    p_sim = sub.add_parser("simulate", help="Interactive CLI simulator")
    p_sim.add_argument("--config", default="config.json", help="Config file")
    p_sim.add_argument("--script", default="main.py", help="Device script")

    # check
    p_chk = sub.add_parser("check", help="Validate config.json")
    p_chk.add_argument("--config", default="config.json")

    # version
    sub.add_parser("version", help="Print WISP version")

    args = parser.parse_args()

    if args.command == "new":
        cmd_new(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "simulate":
        cmd_simulate(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "version":
        cmd_version()
    else:
        parser.print_help()


# ------------------------------------------------------------------ #
# Commands                                                            #
# ------------------------------------------------------------------ #

def cmd_new(args: argparse.Namespace) -> None:
    name = args.name.lower().replace(" ", "_").replace("-", "_")
    template = args.template
    dest = Path(name)

    if dest.exists():
        print(f"❌  Directory '{name}' already exists.")
        sys.exit(1)

    dest.mkdir(parents=True)

    _write_template(dest, name, template)

    print(f"""
✅  WISP project '{name}' created!

   cd {name}
   # Edit config.json — add your Telegram token and AI API key
   wisp run            # start with Telegram transport
   wisp simulate       # test interactively without Telegram
""")


def cmd_run(args: argparse.Namespace) -> None:
    script = Path(args.script)
    if not script.exists():
        print(f"❌  Script not found: {script}")
        print("    Run 'wisp new <name>' to create a project.")
        sys.exit(1)

    # Inject transport override via env var
    os.environ.setdefault("WISP_TRANSPORT", args.transport)
    _exec_script(script)


def cmd_simulate(args: argparse.Namespace) -> None:
    script = Path(args.script)
    if not script.exists():
        print(f"❌  Script not found: {script}")
        sys.exit(1)
    os.environ["WISP_TRANSPORT"] = "cli"
    _exec_script(script)


def cmd_check(args: argparse.Namespace) -> None:
    from wisp.core.config import WispConfig
    from wisp.core.errors import ConfigurationError
    path = Path(args.config)
    if not path.exists():
        print(f"❌  Config not found: {path}")
        sys.exit(1)
    try:
        config = WispConfig.from_file(path)
        config.validate()
        import json
        print("✅  Config is valid:")
        print(json.dumps(config.dump(), indent=2))
    except ConfigurationError as exc:
        print(f"❌  Config error: {exc}")
        sys.exit(1)


def cmd_version() -> None:
    from wisp import __version__
    print(f"wisp-ai {__version__}")


# ------------------------------------------------------------------ #
# Templates                                                           #
# ------------------------------------------------------------------ #

_TEMPLATES = {
    "basic": {
        "main.py": '''\
"""
My WISP device — edit capabilities below and run:
    wisp run             (Telegram)
    wisp simulate        (local CLI)
"""

from wisp import WispDevice, capability


class MyDevice(WispDevice):
    device_name = "{name}"
    description = "A WISP-powered device"

    @capability
    def status(self) -> dict:
        """Report device status."""
        return {{"status": "online", "device": "{name}"}}

    # Add more capabilities here:
    #
    # @capability
    # def read_temperature(self) -> dict:
    #     """Read ambient temperature."""
    #     bme = self.hardware.sensor("bme280")
    #     return {{"temperature": bme.temperature, "unit": "C"}}
    #
    # @capability
    # def toggle_relay(self, state: str) -> dict:
    #     """Turn the relay on or off.\"""
    #     self.hardware.set_output("relay_1", state == "on")
    #     return {{"relay_1": state}}


if __name__ == "__main__":
    device = MyDevice.from_config("config.json")
    device.run()
''',
        "config.json": '''\
{{
  "device_name": "{name}",
  "wifi": {{
    "ssid": "YourWiFi",
    "password": "YourPassword"
  }},
  "telegram": {{
    "token": "YOUR_TELEGRAM_BOT_TOKEN"
  }},
  "ai": {{
    "provider": "groq",
    "api_key": "YOUR_GROQ_API_KEY",
    "model": "llama-3.3-70b-versatile",
    "max_tokens": 1024
  }},
  "hardware": {{
    "i2c_sda": 21,
    "i2c_scl": 22,
    "gpio_outputs": {{
      "relay_1": 5,
      "led_1": 18
    }}
  }}
}}
''',
    },

    "sensors": {
        "main.py": '''\
"""
WISP sensor hub — reads BME280, BH1750 sensors.
Wire sensors to I2C and run: wisp run
"""

from wisp import WispDevice, capability


class SensorHub(WispDevice):
    device_name = "{name}"
    description = "Environmental sensor hub"

    @capability
    def read_all(self) -> dict:
        """Read all connected sensors at once."""
        results = {{}}
        for cap in self.capabilities.all():
            if cap.name.startswith("read_") and cap.name != "read_all":
                try:
                    results.update(cap(self))
                except Exception:
                    pass
        return results


if __name__ == "__main__":
    device = SensorHub.from_config("config.json")
    device.run()   # auto-discovers I2C sensors from config
''',
        "config.json": '''\
{{
  "device_name": "{name}",
  "telegram": {{
    "token": "YOUR_TELEGRAM_BOT_TOKEN"
  }},
  "ai": {{
    "provider": "groq",
    "api_key": "YOUR_GROQ_API_KEY",
    "model": "llama-3.3-70b-versatile"
  }},
  "hardware": {{
    "i2c_bus": 1,
    "gpio_outputs": {{}}
  }}
}}
''',
    },

    "ros2": {
        "main.py": '''\
"""
WISP ROS2 robot — natural language control via Telegram.

source /opt/ros/$ROS_DISTRO/setup.bash
wisp run
"""

from wisp import WispDevice, capability
from wisp.plugins.ros2 import ROS2Plugin


class MyRobot(WispDevice):
    device_name = "{name}"
    description = "ROS2 robot — TurtleBot3 / Husky / custom"

    @capability
    def status(self) -> dict:
        """Report robot status."""
        return {{"status": "online", "robot": "{name}"}}


if __name__ == "__main__":
    device = MyRobot.from_config("config.json")
    device.use(ROS2Plugin())
    device.run()
''',
        "config.json": '''\
{{
  "device_name": "{name}",
  "telegram": {{
    "token": "YOUR_TELEGRAM_BOT_TOKEN"
  }},
  "ai": {{
    "provider": "groq",
    "api_key": "YOUR_GROQ_API_KEY",
    "model": "llama-3.3-70b-versatile",
    "max_tokens": 2048
  }},
  "hardware": {{
    "gpio_outputs": {{}}
  }}
}}
''',
    },
}


def _write_template(dest: Path, name: str, template_name: str) -> None:
    template = _TEMPLATES.get(template_name, _TEMPLATES["basic"])
    for filename, content in template.items():
        filled = content.format(name=name)
        (dest / filename).write_text(filled, encoding="utf-8")
        print(f"  Created {dest / filename}")


def _exec_script(script: Path) -> None:
    """Execute a Python script in the context of its directory."""
    script = script.resolve()
    sys.path.insert(0, str(script.parent))
    os.chdir(script.parent)
    with open(script, encoding="utf-8") as f:
        code = compile(f.read(), str(script), "exec")
    glob = {"__name__": "__main__", "__file__": str(script)}
    exec(code, glob)  # noqa: S102


if __name__ == "__main__":
    main()
