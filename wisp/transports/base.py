"""WISP transport base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wisp.core.device import WispDevice


class BaseTransport(ABC):
    """Abstract base class for all WISP transports."""

    def __init__(self, device: "WispDevice") -> None:
        self.device = device

    @abstractmethod
    def start(self) -> None:
        """Start the transport (blocking)."""

    def stop(self) -> None:
        """Gracefully stop the transport."""
