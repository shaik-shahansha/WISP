"""
WISP HTTP transport — simple webhook server.

Starts a lightweight HTTP server on localhost.
Useful for integrating WISP into web apps, n8n, Make, etc.

POST /message
    Body: {"user": "alice", "text": "turn on the fan"}
    Returns: {"reply": "✅ relay_1 -> ON"}

GET /capabilities
    Returns: [{"name": "...", "description": "..."}]

GET /health
    Returns: {"status": "ok", "device": "...", "capabilities": [...]}
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

from wisp.transports.base import BaseTransport
from wisp.core.errors import TransportError

if TYPE_CHECKING:
    from wisp.core.device import WispDevice

logger = logging.getLogger("wisp.transport.http")

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080


class HTTPTransport(BaseTransport):
    """
    Minimal HTTP webhook transport.

    Configuration (optional, via config.json)::

        "transport": {
            "host": "0.0.0.0",
            "port": 8080
        }
    """

    def __init__(self, device: "WispDevice") -> None:
        super().__init__(device)
        raw = device.config._raw.get("transport", {})
        self._host = raw.get("host", DEFAULT_HOST)
        self._port = int(raw.get("port", DEFAULT_PORT))

    def start(self) -> None:
        device = self.device
        logger.info("HTTP transport listening on http://%s:%d", self._host, self._port)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                logger.debug(fmt, *args)

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    self._json(200, {
                        "status": "ok",
                        "device": device.name,
                        "capabilities": device.capabilities.names(),
                    })
                elif self.path == "/capabilities":
                    self._json(200, device.capabilities.to_ai_schema())
                else:
                    self._json(404, {"error": "Not found"})

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/message":
                    self._json(404, {"error": "Not found"})
                    return
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    self._json(400, {"error": "Invalid JSON"})
                    return

                user = payload.get("user", "http_user")
                text = payload.get("text", "")
                if not text:
                    self._json(400, {"error": "Missing 'text' field"})
                    return

                reply = device.process_message(user=user, text=text)
                self._json(200, {"reply": reply})

            def _json(self, status: int, data: Any) -> None:
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer((self._host, self._port), Handler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("HTTP transport stopped.")
        finally:
            server.server_close()
