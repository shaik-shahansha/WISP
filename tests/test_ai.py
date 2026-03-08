"""Tests for WISP AI layer."""

import json
import pytest

from wisp.ai.prompt import build_system_prompt
from wisp.ai.client import _parse_response
from wisp.core.errors import AIError


class TestPromptBuilder:

    def test_basic_prompt(self):
        caps = [{"name": "read_temp", "description": "Read temperature"}]
        prompt = build_system_prompt("my_device", caps)
        assert "my_device" in prompt
        assert "read_temp" in prompt
        assert "Read temperature" in prompt

    def test_prompt_contains_rules(self):
        prompt = build_system_prompt("dev", [])
        assert "action" in prompt.lower()
        assert "json" in prompt.lower()

    def test_device_description_included(self):
        prompt = build_system_prompt("dev", [], device_description="A cool robot")
        assert "A cool robot" in prompt

    def test_no_capabilities_still_valid(self):
        prompt = build_system_prompt("dev", [])
        assert "dev" in prompt


class TestResponseParser:

    def test_plain_json(self):
        raw = '{"action": "read_temp"}'
        result = _parse_response(raw)
        assert result == {"action": "read_temp"}

    def test_json_with_args(self):
        raw = '{"action": "set_relay", "relay_name": "fan", "state": "on"}'
        result = _parse_response(raw)
        assert result["action"] == "set_relay"
        assert result["state"] == "on"

    def test_strips_markdown_fences(self):
        raw = "```json\n{\"action\": \"ping\"}\n```"
        result = _parse_response(raw)
        assert result["action"] == "ping"

    def test_error_response(self):
        raw = '{"error": "No camera capability. I have: read_temp"}'
        result = _parse_response(raw)
        assert "error" in result

    def test_json_embedded_in_text(self):
        raw = 'Here is the command: {"action": "read_light"} Hope that helps!'
        result = _parse_response(raw)
        assert result["action"] == "read_light"

    def test_invalid_json_raises(self):
        with pytest.raises(AIError):
            _parse_response("this is not json")

    def test_non_object_raises(self):
        with pytest.raises(AIError):
            _parse_response("[1, 2, 3]")
