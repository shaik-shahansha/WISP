"""
WISP Telegram transport.

Long-polls the Telegram Bot API for messages, passes them to the device,
and sends replies back. No external libraries required — uses urllib only.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wisp.transports.base import BaseTransport
from wisp.core.errors import TransportError

if TYPE_CHECKING:
    from wisp.core.device import WispDevice

logger = logging.getLogger("wisp.transport.telegram")

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
POLL_TIMEOUT = 30    # seconds for long-poll
RETRY_DELAY = 5      # seconds before retrying after an error


class TelegramTransport(BaseTransport):
    """
    Telegram bot transport.

    Polls getUpdates, forwards messages to ``device.process_message()``,
    sends the reply via sendMessage.
    """

    def __init__(self, device: "WispDevice") -> None:
        super().__init__(device)
        self._token = device.config.telegram.token
        self._allowed_users: List[int] = device.config.telegram.allowed_users
        self._offset = 0
        self._running = False
        # Each incoming message is dispatched to a thread so the poll loop
        # remains live while the AI HTTP call is in flight.
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="wisp-msg")

    # ------------------------------------------------------------------ #
    # Public                                                               #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        logger.info("Telegram transport starting — polling for messages…")
        self._running = True
        self._verify_token()
        self._poll_loop()

    def stop(self) -> None:
        self._running = False
        self._executor.shutdown(wait=False)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _verify_token(self) -> None:
        try:
            me = self._api("getMe")
            name = me.get("result", {}).get("username", "?")
            logger.info("Telegram bot: @%s  (ready)", name)
        except Exception as exc:  # noqa: BLE001
            raise TransportError(f"Invalid Telegram token: {exc}") from exc

    def _poll_loop(self) -> None:
        while self._running:
            try:
                updates = self._api(
                    "getUpdates",
                    {"timeout": POLL_TIMEOUT, "offset": self._offset, "allowed_updates": ["message"]},
                )
                for update in updates.get("result", []):
                    self._handle_update(update)
            except KeyboardInterrupt:
                logger.info("Telegram transport stopped.")
                break
            except TransportError as exc:
                logger.error("Transport error: %s — retrying in %ds", exc, RETRY_DELAY)
                time.sleep(RETRY_DELAY)
            except Exception as exc:  # noqa: BLE001
                logger.error("Unexpected error: %s — retrying in %ds", exc, RETRY_DELAY)
                time.sleep(RETRY_DELAY)

    def _handle_update(self, update: Dict[str, Any]) -> None:
        self._offset = update["update_id"] + 1

        message = update.get("message")
        if not message:
            return

        chat_id: int = message["chat"]["id"]
        user_id: int = message["from"]["id"]
        username: str = message["from"].get("username") or message["from"].get("first_name", "user")
        text: str = message.get("text", "").strip()

        if not text:
            return

        # Optional user whitelist
        if self._allowed_users and user_id not in self._allowed_users:
            logger.warning("Ignored message from unauthorized user %d", user_id)
            self._send(chat_id, "⛔ Unauthorized.")
            return

        logger.info("[%s] %s", username, text)

        # Dispatch to thread pool so the poll loop isn't blocked by the AI call
        self._executor.submit(self._process_and_reply, chat_id, username, text)

    def _process_and_reply(self, chat_id: int, username: str, text: str) -> None:
        try:
            reply = self.device.process_message(user=username, text=text)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unhandled error processing message from %s: %s", username, exc)
            reply = self.device.on_error(exc)
        self._send(chat_id, reply)

    def _send(self, chat_id: int, text: str) -> None:
        try:
            self._api("sendMessage", {"chat_id": chat_id, "text": text})
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to send message: %s", exc)

    def _api(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = TELEGRAM_API.format(token=self._token, method=method)
        if params:
            data = json.dumps(params).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        else:
            req = urllib.request.Request(url)

        try:
            with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            raise TransportError(f"Telegram API error {exc.code}: {body}") from exc
        except Exception as exc:  # noqa: BLE001
            raise TransportError(f"Telegram request failed: {exc}") from exc
