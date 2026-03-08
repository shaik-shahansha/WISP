"""
WISP unified AI client.

Wraps Groq and OpenRouter behind a single interface.
Parses the AI response JSON into a capability command dict.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from wisp.ai.prompt import build_system_prompt
from wisp.core.config import AIConfig
from wisp.core.errors import AIError

logger = logging.getLogger("wisp.ai")

# Retry policy for transient AI API failures (network blips, 429 rate-limits)
_AI_RETRIES = 3
_AI_BACKOFF_BASE = 1.5  # seconds; delay = base ** attempt (1.5s, 2.25s, 3.375s)


class AIClient:
    """
    Unified client that talks to the configured AI provider and parses responses.

    Usage::

        client = AIClient(config.ai)
        command = client.parse(
            user_message="turn on the fan",
            capabilities=[{"name": "set_relay", "description": "..."}],
            device_name="my_device",
        )
        # command == {"action": "set_relay", "relay_name": "fan", "state": "on"}
    """

    def __init__(self, config: AIConfig) -> None:
        self._config = config
        self._provider = _build_provider(config)

    def parse(
        self,
        user_message: str,
        capabilities: List[Dict[str, Any]],
        device_name: str = "wisp_device",
        device_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a user message + capability schema to the AI.
        Returns a parsed command dict.
        """
        system_prompt = build_system_prompt(
            device_name=device_name,
            capabilities=capabilities,
            device_description=device_description,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        logger.debug("AI request: %r", user_message)

        last_exc: Exception = AIError("No attempts made")
        for attempt in range(_AI_RETRIES):
            try:
                raw = self._provider.complete(messages)
                break
            except AIError as exc:
                last_exc = exc
                if attempt < _AI_RETRIES - 1:
                    delay = _AI_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        "AI request failed (attempt %d/%d): %s — retrying in %.1fs",
                        attempt + 1, _AI_RETRIES, exc, delay,
                    )
                    time.sleep(delay)
        else:
            raise last_exc

        logger.debug("AI raw response: %r", raw)
        return _parse_response(raw)

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def model(self) -> str:
        return self._config.model


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _build_provider(config: AIConfig) -> Any:
    provider = config.provider.lower()
    if provider == "groq":
        from wisp.ai.providers.groq import GroqProvider
        return GroqProvider(
            api_key=config.api_key,
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
    elif provider == "openrouter":
        from wisp.ai.providers.openrouter import OpenRouterProvider
        return OpenRouterProvider(
            api_key=config.api_key,
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
    else:
        raise AIError(
            f"Unknown AI provider '{provider}'. "
            "Supported: groq, openrouter. "
            "See docs/PROVIDERS.md."
        )


def _parse_response(raw: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from the AI response.
    Handles markdown code fences, leading text, etc.
    """
    # Strip markdown fences
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    # Find JSON object in response
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AIError(f"AI returned non-JSON response: {raw!r}") from exc

    if not isinstance(data, dict):
        raise AIError(f"AI response must be a JSON object, got: {type(data).__name__}")

    return data
