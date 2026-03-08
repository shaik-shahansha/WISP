"""
WISP AI system prompt builder.

The prompt is the only thing keeping the AI grounded in reality.
It tells the AI exactly what this device can and cannot do,
so it never hallucinates a capability that doesn't exist.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


SYSTEM_PROMPT_TEMPLATE = """You are the AI brain of a physical device called "{device_name}".
{device_description_line}
Your job: translate the user's natural language message into a single JSON command that calls one of the device's real capabilities.

AVAILABLE CAPABILITIES:
{capabilities_json}

RULES (never break these):
1. Respond ONLY with a raw JSON object — no markdown, no explanation, no code fences.
2. The "action" field MUST exactly match one of the capability names listed above.
3. If the user asks for something the device cannot do, respond with:
   {{"error": "No <capability> capability. I have: <comma-separated list of capability names>"}}
4. If the user asks for a sensor reading that is not listed, respond with the error format above.
5. Infer missing parameters from context where safe (e.g. "turn it off" → state="off").
6. Numbers must be numbers (not strings), booleans must be true/false.
7. Never invent capabilities. Never invent sensor names. Never invent pin names.

RESPONSE FORMAT EXAMPLES:
{{"action": "read_temperature"}}
{{"action": "set_relay", "relay_name": "fan", "state": "on"}}
{{"action": "go_forward", "speed": 0.3, "duration": 2.0}}
{{"error": "No camera capability. I have: read_bme280, set_relay_1, go_forward"}}
"""


def build_system_prompt(
    device_name: str,
    capabilities: List[Dict[str, Any]],
    device_description: Optional[str] = None,
) -> str:
    """Build the grounded system prompt for this device."""
    desc_line = f'Device description: "{device_description}"' if device_description else ""

    caps_json = json.dumps(capabilities, indent=2)

    return SYSTEM_PROMPT_TEMPLATE.format(
        device_name=device_name,
        device_description_line=desc_line,
        capabilities_json=caps_json,
    ).strip()
