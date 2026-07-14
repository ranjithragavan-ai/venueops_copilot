"""
Tests for services/ai_service.py — the Gemini AI triage and chat layer.

Covers:
- Stadium context loading and auto-refresh logic.
- Triage incident when API key is missing.
- Chat when API key is missing.
- TicketSchema completeness.
"""

import json
import datetime
import pytest
from services.ai_service import (
    load_stadium_context,
    triage_incident,
    chat_with_copilot,
    TicketSchema,
)


# ───────────────────────────────────────────────────────────────────── #
#  Stadium Context Tests
# ───────────────────────────────────────────────────────────────────── #

class TestLoadStadiumContext:
    """Verify the JSON-based context loader."""

    def test_returns_dict_and_list(self, mocker):
        mock_state = {"match_start_time": "2026-07-20T18:00:00Z", "current_attendance": 50000}
        mock_sops = [{"id": "SOP-01", "title": "Medical Emergency"}]
        mocker.patch("builtins.open", mocker.mock_open(read_data=""))
        mocker.patch("json.load", side_effect=[mock_state, mock_sops])
        ctx, sops = load_stadium_context()
        assert ctx["current_attendance"] == 50000
        assert len(sops) == 1

    def test_returns_empty_on_file_error(self, mocker):
        mocker.patch("builtins.open", side_effect=FileNotFoundError("missing"))
        ctx, sops = load_stadium_context()
        assert ctx == {}
        assert sops == []


# ───────────────────────────────────────────────────────────────────── #
#  Triage Tests
# ───────────────────────────────────────────────────────────────────── #

class TestTriageIncident:
    """Verify triage behaviour when the API key is not configured."""

    def test_triage_without_api_key_returns_error(self, mocker):
        mocker.patch("services.ai_service.client", None)
        result = triage_incident("There is a fire near Gate A")
        assert "error" in result
        assert "API Key" in result["error"]


# ───────────────────────────────────────────────────────────────────── #
#  Chat Tests
# ───────────────────────────────────────────────────────────────────── #

class TestChatWithCopilot:
    """Verify chat behaviour when the API key is not configured."""

    def test_chat_without_api_key_returns_offline(self, mocker):
        mocker.patch("services.ai_service.client", None)
        result = chat_with_copilot([], "What gates are open?")
        assert "offline" in result.lower()


# ───────────────────────────────────────────────────────────────────── #
#  Schema Validation
# ───────────────────────────────────────────────────────────────────── #

class TestTicketSchema:
    """Ensure the structured output schema has all required fields."""

    EXPECTED_FIELDS = [
        "incident_type", "severity", "location", "building", "floor",
        "action_required", "sop_reference", "required_role", "escalation_contact",
    ]

    def test_all_required_fields_present(self):
        schema = TicketSchema.schema
        for field in self.EXPECTED_FIELDS:
            assert field in schema["properties"], f"Missing field: {field}"
            assert field in schema["required"], f"Field not required: {field}"

    def test_schema_field_types(self):
        for prop in TicketSchema.schema["properties"].values():
            assert prop["type"] == "STRING"
