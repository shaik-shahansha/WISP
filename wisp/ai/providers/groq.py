"""
WISP Groq AI provider.

Docs: https://console.groq.com/docs/openai
Free tier: ~14,400 req/day, no credit card.
Best model: llama-3.3-70b-versatile
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from wisp.core.errors import AIError


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider:
    """Client for the Groq AI API (OpenAI-compatible)."""

    name = "groq"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile", max_tokens: int = 1024, temperature: float = 0.1) -> None:
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Send messages to Groq and return the response content string."""
        import urllib.request

        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            GROQ_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "groq-python/0.18.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise AIError(f"Groq HTTP error {exc.code}: {exc.read().decode()}") from exc
        except Exception as exc:  # noqa: BLE001
            raise AIError(f"Groq request failed: {exc}") from exc

        try:
            return body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise AIError(f"Unexpected Groq response format: {body}") from exc
