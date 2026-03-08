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
    async def start(self) -> None:
        """Start the transport (runs until stopped)."""

    def stop(self) -> None:
        """Gracefully stop the transport."""


async def _run_blocking(fn, *args):
    """
    Run a blocking function without stalling the event loop.

    On CPython uses ``loop.run_in_executor`` (thread pool).
    On MicroPython (no threadpool) calls directly — the event loop
    yields between tasks so short blocking calls are acceptable.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    if hasattr(loop, "run_in_executor"):
        return await loop.run_in_executor(None, fn, *args)
    return fn(*args)  # MicroPython: call directly
