"""
WISP CLI transport — interactive terminal conversation.

Use this for local testing without a Telegram bot.

    device.run(transport="cli")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wisp.transports.base import BaseTransport

if TYPE_CHECKING:
    from wisp.core.device import WispDevice

logger = logging.getLogger("wisp.transport.cli")

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║            WISP — Natural Language Device Control           ║
║                  CLI transport  (test mode)                 ║
╚══════════════════════════════════════════════════════════════╝
Device : {device_name}
AI     : {provider}/{model}
Caps   : {capabilities}

Type your command, or "quit" / Ctrl+C to exit.
"""


class CLITransport(BaseTransport):
    """Interactive REPL transport for testing without Telegram."""

    def start(self) -> None:
        device = self.device
        caps = ", ".join(device.capabilities.names())
        print(
            BANNER.format(
                device_name=device.name,
                provider=device.config.ai.provider,
                model=device.config.ai.model,
                capabilities=caps or "(none)",
            )
        )

        while True:
            try:
                text = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break

            if not text:
                continue
            if text.lower() in ("quit", "exit", "q"):
                print("Goodbye.")
                break

            reply = device.process_message(user="cli_user", text=text)
            print(f"WISP: {reply}\n")
