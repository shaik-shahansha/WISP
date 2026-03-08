"""
WISP OpenRouter AI provider.

Docs: https://openrouter.ai/docs
Free tier: 200 req/day on free models.
Best free model: meta-llama/llama-3.3-70b-instruct:free
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from wisp.core.errors import AIError


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider:
    """Client for the OpenRouter AI API (OpenAI-compatible)."""

    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
        max_tokens: int = 1024,
        temperature: float = 0.1,
        site_url: str = "https://github.com/shaik-shahansha/wisp",
        site_name: str = "WISP",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.site_url = site_url
        self.site_name = site_name

    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Send messages to OpenRouter and return the response content string."""
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
            OPENROUTER_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": self.site_url,
                "X-Title": self.site_name,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise AIError(f"OpenRouter HTTP error {exc.code}: {exc.read().decode()}") from exc
        except Exception as exc:  # noqa: BLE001
            raise AIError(f"OpenRouter request failed: {exc}") from exc

        try:
            return body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise AIError(f"Unexpected OpenRouter response format: {body}") from exc
