"""
WISP WispDevice — the base class for every WISP-powered device.

Subclass WispDevice, decorate methods with @capability, call .run().

    from wisp import WispDevice, capability

    class TemperatureMonitor(WispDevice):

        @capability
        def read_temperature(self) -> dict:
            \"\"\"Read the current temperature and humidity.\"\"\"
            bme = self.hardware.sensor("bme280")
            return {
                "temperature": bme.temperature,
                "humidity": bme.humidity,
            }

    if __name__ == "__main__":
        device = TemperatureMonitor.from_config("config.json")
        device.run()
"""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type

from wisp.core.capability import CapabilityRegistry, CapabilitySpec
from wisp.core.config import WispConfig
from wisp.core.errors import CapabilityError, ConfigurationError

logger = logging.getLogger("wisp.device")


class WispDeviceMeta(type):
    """
    Metaclass that automatically builds a CapabilityRegistry for every
    WispDevice subclass by scanning for methods marked with @capability.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple,
        namespace: Dict[str, Any],
        **kwargs: Any,
    ) -> "WispDeviceMeta":
        registry = CapabilityRegistry()

        # Inherit parent capabilities
        for base in bases:
            if hasattr(base, "_wisp_registry"):
                for spec in base._wisp_registry.all():
                    registry.register(spec)

        # Register capabilities defined on this class
        for attr_name, attr_value in namespace.items():
            if callable(attr_value) and hasattr(attr_value, "_wisp_capability"):
                spec: CapabilitySpec = attr_value._wisp_capability
                registry.register(spec)

        namespace["_wisp_registry"] = registry
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        return cls


class WispDevice(metaclass=WispDeviceMeta):
    """
    Base class for all WISP-powered devices.

    Subclass this, add ``@capability``-decorated methods, then call
    ``device.run()`` to start listening for natural language commands.

    Class-level attributes
    ----------------------
    device_name : str
        Human-readable name (overrides config device_name).
    description : str
        One-sentence description sent to the AI as context.
    """

    device_name: str = ""
    description: str = ""

    # Set by metaclass
    _wisp_registry: CapabilityRegistry

    def __init__(self, config: Optional[WispConfig] = None) -> None:
        self._config = config
        self._hardware: Optional[Any] = None   # HardwareLayer, lazy
        self._transport: Optional[Any] = None  # Transport, set at run()
        self._ai_client: Optional[Any] = None  # AIClient, set at run()
        self._plugins: list = []

        self._logger = logging.getLogger(f"wisp.{self.__class__.__name__}")

    # ------------------------------------------------------------------ #
    # Factory / alternate constructors                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_config(
        cls: Type["WispDevice"],
        path: str | Path = "config.json",
    ) -> "WispDevice":
        """Create a device instance by loading ``config.json``."""
        config = WispConfig.from_file(path)
        return cls(config=config)

    @classmethod
    def from_env(cls: Type["WispDevice"]) -> "WispDevice":
        """Create a device instance from environment variables."""
        config = WispConfig.from_env()
        return cls(config=config)

    # ------------------------------------------------------------------ #
    # Plugin support                                                      #
    # ------------------------------------------------------------------ #

    def use(self, plugin: Any) -> "WispDevice":
        """
        Attach a plugin to this device.

        Plugins can register additional capabilities without subclassing.

            device = MyDevice.from_config("config.json")
            device.use(ROS2Plugin())
            device.run()

        Returns ``self`` for chaining.
        """
        self._plugins.append(plugin)
        plugin.attach(self)
        return self

    def add_capability(self, spec: CapabilitySpec) -> None:
        """
        Register a capability on this device instance at runtime.

        Use this inside a plugin's ``attach()`` method instead of
        accessing the private ``_wisp_registry`` directly::

            class MyPlugin(WispPlugin):
                def attach(self, device):
                    spec = CapabilitySpec(
                        name="do_thing",
                        description="Does the thing",
                        fn=self._do_thing,
                    )
                    device.add_capability(spec)  # preferred public API
        """
        self._wisp_registry.register(spec)

    # ------------------------------------------------------------------ #
    # Properties                                                          #
    # ------------------------------------------------------------------ #

    @property
    def config(self) -> WispConfig:
        if self._config is None:
            raise ConfigurationError(
                "No config provided. Use WispDevice.from_config('config.json') "
                "or pass a WispConfig object to the constructor."
            )
        return self._config

    @property
    def hardware(self) -> Any:
        """Lazily initialised HardwareLayer."""
        if self._hardware is None:
            from wisp.hardware.hal import HardwareLayer
            self._hardware = HardwareLayer(self.config.hardware)
            self._hardware.boot()
        return self._hardware

    @property
    def capabilities(self) -> CapabilityRegistry:
        return self._wisp_registry

    @property
    def name(self) -> str:
        return self.device_name or self.config.device_name

    # ------------------------------------------------------------------ #
    # Capability execution                                                #
    # ------------------------------------------------------------------ #

    def execute(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an AI-parsed command dict.

        Expected format::

            {"action": "read_temperature"}
            {"action": "set_relay", "relay_name": "fan", "state": "on"}

        Returns a result dict that is formatted and sent back to the user.
        """
        action = command.get("action", "").strip()
        if not action:
            return {"error": "No action specified."}

        spec = self._wisp_registry.get(action)
        if spec is None:
            available = ", ".join(self._wisp_registry.names())
            raise CapabilityError(
                f"Unknown action '{action}'. Available: {available}"
            )

        kwargs = {k: v for k, v in command.items() if k != "action"}
        self._logger.info("Executing capability '%s' with %s", action, kwargs)

        try:
            result = spec(self, **kwargs)
        except TypeError as exc:
            raise CapabilityError(f"Bad parameters for '{action}': {exc}") from exc

        if result is None:
            result = {"status": "ok"}
        return result

    # ------------------------------------------------------------------ #
    # Lifecycle hooks (optional overrides)                               #
    # ------------------------------------------------------------------ #

    def on_boot(self) -> None:
        """Called once after hardware is initialised, before the transport starts."""

    def on_message(self, user: str, text: str) -> Optional[str]:
        """
        Called for every incoming message **before** AI processing.
        Return a string to short-circuit AI and reply immediately,
        or ``None`` to proceed normally.
        """
        return None

    def on_reply(self, user: str, reply: str) -> str:
        """
        Called with the final reply string before it is sent.
        Override to add custom formatting, logging, etc.
        """
        return reply

    def on_error(self, exc: Exception) -> str:
        """Called when an unhandled error occurs. Returns the error message to send."""
        return f"❌ Error: {exc}"

    # ------------------------------------------------------------------ #
    # Run                                                                 #
    # ------------------------------------------------------------------ #

    def run(
        self,
        transport: Optional[str] = None,
        *,
        auto_discover_hardware: bool = True,
        log_level: str = "INFO",
    ) -> None:
        """
        Start the device.

        Parameters
        ----------
        transport : str, optional
            ``"telegram"`` (default), ``"cli"``, or ``"http"``.
        auto_discover_hardware : bool
            Scan the I2C bus at boot and register discovered sensors
            as additional read capabilities.
        log_level : str
            Python logging level string, default ``"INFO"``.
        """
        _setup_logging(log_level)

        self.config.validate()

        chosen_transport = transport or "telegram"

        self._logger.info(
            "WISP %s booting  (device=%s  transport=%s  ai=%s/%s)",
            _version(),
            self.name,
            chosen_transport,
            self.config.ai.provider,
            self.config.ai.model,
        )

        # Auto-discover I2C sensors and add them as capabilities
        if auto_discover_hardware:
            self._auto_discover()

        # Print capability list
        caps = self._wisp_registry.all()
        self._logger.info(
            "Capabilities (%d): %s",
            len(caps),
            ", ".join(c.name for c in caps),
        )

        # Call user hook
        self.on_boot()

        # Start the AI client
        from wisp.ai.client import AIClient
        self._ai_client = AIClient(self.config.ai)

        # Start the transport
        if chosen_transport == "telegram":
            from wisp.transports.telegram import TelegramTransport
            self._transport = TelegramTransport(self)
        elif chosen_transport == "cli":
            from wisp.transports.cli import CLITransport
            self._transport = CLITransport(self)
        elif chosen_transport == "http":
            from wisp.transports.http import HTTPTransport
            self._transport = HTTPTransport(self)
        else:
            raise ConfigurationError(
                f"Unknown transport '{chosen_transport}'. "
                "Available: telegram, cli, http"
            )

        self._transport.start()

    # ------------------------------------------------------------------ #
    # Auto-discovery                                                      #
    # ------------------------------------------------------------------ #

    def _auto_discover(self) -> None:
        """Scan I2C bus and register sensor read capabilities."""
        try:
            from wisp.hardware.scanner import I2CScanner
            hw_cfg = self.config.hardware

            scanner = I2CScanner(
                sda=hw_cfg.i2c_sda,
                scl=hw_cfg.i2c_scl,
                freq=hw_cfg.i2c_freq,
                bus=hw_cfg.i2c_bus,
            )
            discovered = scanner.scan()

            for sensor_name, sensor_obj in discovered.items():
                self._register_sensor_capability(sensor_name, sensor_obj)
                self._logger.info("  Discovered sensor: %s", sensor_name)

        except Exception as exc:  # noqa: BLE001
            self._logger.debug("Hardware auto-discovery skipped: %s", exc)

        # Register GPIO output capabilities
        for output_name, pin in self.config.hardware.gpio_outputs.items():
            self._register_gpio_capability(output_name, pin)
            self._logger.info("  GPIO output: %s (pin %s)", output_name, pin)

    def _register_sensor_capability(self, sensor_name: str, sensor_obj: Any) -> None:
        from wisp.core.capability import CapabilitySpec

        def read_fn(self_dev: "WispDevice", _name: str = sensor_name, _obj: Any = sensor_obj) -> Dict[str, Any]:
            return _obj.read()

        spec = CapabilitySpec(
            name=f"read_{sensor_name}",
            description=f"Read all values from the {sensor_name.upper()} sensor",
            fn=read_fn,
        )
        self._wisp_registry.register(spec)

    def _register_gpio_capability(self, output_name: str, pin: int) -> None:
        from wisp.core.capability import CapabilitySpec, CapabilityParam

        def control_fn(
            self_dev: "WispDevice",
            state: str,
            _name: str = output_name,
            _pin: int = pin,
        ) -> Dict[str, Any]:
            self_dev.hardware.set_output(_name, state == "on" or state is True)
            return {"output": _name, "state": state}

        spec = CapabilitySpec(
            name=f"set_{output_name}",
            description=f"Turn the {output_name} on or off",
            fn=control_fn,
            parameters=[
                CapabilityParam(
                    name="state",
                    type="str",
                    description="'on' or 'off'",
                )
            ],
        )
        self._wisp_registry.register(spec)

    # ------------------------------------------------------------------ #
    # AI message processing (called by transports)                       #
    # ------------------------------------------------------------------ #

    def process_message(self, user: str, text: str) -> str:
        """
        Full pipeline: natural language → AI → execute capability → reply.
        Called internally by transports.
        """
        # User hook may short-circuit
        hook_reply = self.on_message(user, text)
        if hook_reply is not None:
            return hook_reply

        if self._ai_client is None:
            return "❌ AI client not initialised."

        try:
            command = self._ai_client.parse(
                user_message=text,
                capabilities=self._wisp_registry.to_ai_schema(),
                device_name=self.name,
                device_description=self.description,
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.error("AI error: %s", exc)
            return self.on_error(exc)

        if "error" in command:
            return f"❌ {command['error']}"

        try:
            result = self.execute(command)
        except CapabilityError as exc:
            return f"❌ {exc}"
        except Exception as exc:  # noqa: BLE001
            return self.on_error(exc)

        reply = _format_result(result)
        return self.on_reply(user, reply)

    def __repr__(self) -> str:
        caps = self._wisp_registry.names()
        return (
            f"<{self.__class__.__name__} "
            f"name={self.name!r} "
            f"capabilities={caps}>"
        )


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _version() -> str:
    try:
        from wisp import __version__
        return __version__
    except ImportError:
        return "?"


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _format_result(result: Dict[str, Any]) -> str:
    """Convert a capability result dict into a human-readable reply."""
    if not isinstance(result, dict):
        return str(result)

    if "error" in result:
        return f"❌ {result['error']}"

    EMOJI = {
        "temperature": "🌡",
        "humidity": "💧",
        "pressure": "📊",
        "light": "💡",
        "lux": "💡",
        "battery": "🔋",
        "accel": "📐",
        "gyro": "🔄",
        "status": "✅",
        "state": "✅",
        "output": "⚡",
        "relay": "⚡",
        "led": "💡",
    }

    lines = []
    for k, v in result.items():
        if k in ("raw", "_meta"):
            continue
        emoji = next((e for key, e in EMOJI.items() if key in k.lower()), "•")
        if isinstance(v, float):
            lines.append(f"{emoji} {k}: {v:.2f}")
        else:
            lines.append(f"{emoji} {k}: {v}")

    return "\n".join(lines) if lines else "✅ Done"
