"""WISP Plugin base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wisp.core.device import WispDevice


class WispPlugin(ABC):
    """
    Base class for WISP plugins.

    Plugins extend a ``WispDevice`` with additional capabilities
    without subclassing it.

        device = MyDevice.from_config("config.json")
        device.use(MyPlugin())
        device.run()
    """

    @abstractmethod
    def attach(self, device: "WispDevice") -> None:
        """
        Called when the plugin is attached to a device.

        Register capabilities using the public API::

            spec = CapabilitySpec(name="my_cap", description="...", fn=self._fn)
            device.add_capability(spec)
        """
