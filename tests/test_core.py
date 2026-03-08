"""Tests for WISP core — capability registry, config, device."""

import pytest
from wisp import WispDevice, capability
from wisp.core.config import WispConfig
from wisp.core.errors import CapabilityError, ConfigurationError


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def minimal_config():
    return WispConfig.from_dict({
        "device_name": "test_device",
        "telegram": {"token": "123:TEST"},
        "ai": {"provider": "groq", "api_key": "gsk_test"},
    })


# ------------------------------------------------------------------ #
# Capability decorator                                                #
# ------------------------------------------------------------------ #

class TestCapabilityDecorator:

    def test_bare_decorator(self):
        class D(WispDevice):
            @capability
            def read_temp(self) -> dict:
                """Read temperature."""
                return {"temperature": 25.0}

        assert "read_temp" in D._wisp_registry.names()

    def test_decorator_with_args(self):
        class D(WispDevice):
            @capability(name="toggle_fan", description="Control the fan relay")
            def set_fan(self, state: str) -> dict:
                return {"fan": state}

        assert "toggle_fan" in D._wisp_registry.names()
        spec = D._wisp_registry.get("toggle_fan")
        assert spec.description == "Control the fan relay"

    def test_docstring_as_description(self):
        class D(WispDevice):
            @capability
            def read_light(self) -> dict:
                """Measure ambient light in lux."""
                return {"lux": 300.0}

        spec = D._wisp_registry.get("read_light")
        assert "lux" in spec.description.lower()

    def test_param_inference(self):
        class D(WispDevice):
            @capability
            def set_relay(self, relay_name: str, state: str) -> dict:
                return {}

        spec = D._wisp_registry.get("set_relay")
        param_names = [p.name for p in spec.parameters]
        assert "relay_name" in param_names
        assert "state" in param_names


# ------------------------------------------------------------------ #
# WispDevice metaclass                                               #
# ------------------------------------------------------------------ #

class TestWispDeviceMeta:

    def test_registry_is_per_class(self):
        class A(WispDevice):
            @capability
            def cap_a(self) -> dict:
                return {}

        class B(WispDevice):
            @capability
            def cap_b(self) -> dict:
                return {}

        assert "cap_a" in A._wisp_registry.names()
        assert "cap_a" not in B._wisp_registry.names()
        assert "cap_b" in B._wisp_registry.names()

    def test_inheritance(self):
        class Base(WispDevice):
            @capability
            def base_cap(self) -> dict:
                return {}

        class Child(Base):
            @capability
            def child_cap(self) -> dict:
                return {}

        assert "base_cap" in Child._wisp_registry.names()
        assert "child_cap" in Child._wisp_registry.names()

    def test_execute_unknown_action(self, minimal_config):
        class D(WispDevice):
            pass

        device = D(config=minimal_config)
        with pytest.raises(CapabilityError):
            device.execute({"action": "nonexistent_action"})

    def test_execute_calls_capability(self, minimal_config):
        class D(WispDevice):
            @capability
            def ping(self) -> dict:
                return {"pong": True}

        device = D(config=minimal_config)
        result = device.execute({"action": "ping"})
        assert result == {"pong": True}

    def test_execute_passes_kwargs(self, minimal_config):
        class D(WispDevice):
            @capability
            def echo(self, message: str) -> dict:
                return {"echo": message}

        device = D(config=minimal_config)
        result = device.execute({"action": "echo", "message": "hello"})
        assert result == {"echo": "hello"}


# ------------------------------------------------------------------ #
# Config                                                              #
# ------------------------------------------------------------------ #

class TestWispConfig:

    def test_from_dict(self):
        config = WispConfig.from_dict({
            "device_name": "my_device",
            "telegram": {"token": "abc:123"},
            "ai": {"provider": "openrouter", "api_key": "sk-or-test"},
        })
        assert config.device_name == "my_device"
        assert config.telegram.token == "abc:123"
        assert config.ai.provider == "openrouter"

    def test_validate_missing_token(self):
        config = WispConfig.from_dict({"ai": {"api_key": "sk_test"}})
        with pytest.raises(ConfigurationError, match="telegram.token"):
            config.validate()

    def test_validate_missing_api_key(self):
        config = WispConfig.from_dict({"telegram": {"token": "123:TEST"}})
        with pytest.raises(ConfigurationError, match="api_key"):
            config.validate()

    def test_dump_hides_secrets(self):
        config = WispConfig.from_dict({
            "telegram": {"token": "secret_token"},
            "ai": {"api_key": "secret_key", "provider": "groq"},
        })
        dump = config.dump()
        assert "secret" not in str(dump)
        assert dump["telegram"]["token"] == "***"


# ------------------------------------------------------------------ #
# Plugin API                                                          #
# ------------------------------------------------------------------ #

class TestPluginAPI:

    def test_use_registers_capabilities(self, minimal_config):
        from wisp.plugins.base import WispPlugin
        from wisp.core.capability import CapabilitySpec

        class MyPlugin(WispPlugin):
            def attach(self, device):
                spec = CapabilitySpec(
                    name="plugin_cap",
                    description="From plugin",
                    fn=lambda self_dev: {"plugin": True},
                )
                device._wisp_registry.register(spec)

        class D(WispDevice):
            pass

        device = D(config=minimal_config)
        device.use(MyPlugin())

        assert "plugin_cap" in device.capabilities.names()

    def test_use_returns_self_for_chaining(self, minimal_config):
        from wisp.plugins.base import WispPlugin

        class NoopPlugin(WispPlugin):
            def attach(self, device):
                pass

        class D(WispDevice):
            pass

        device = D(config=minimal_config)
        result = device.use(NoopPlugin())
        assert result is device
