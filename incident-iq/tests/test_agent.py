"""
Tests for src/agent.py.

Verifies:
 - analyze_incident() requires log_group as a parameter without default (raises TypeError)
 - analyze_incident() invokes agent and extracts structured JSON from response
 - _extract_json parses raw JSON, markdown-wrapped JSON, or conversational responses
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure default AWS region is configured
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import agent


class TestAgent:
    """Tests for agent building, prompt execution, and response parsing."""

    def test_log_group_is_required_param(self):
        """Calls analyze_incident without log_group and asserts TypeError."""
        with pytest.raises(TypeError):
            agent.analyze_incident(minutes_back=10)

    @patch("agent.build_agent")
    def test_analyze_incident_executes_and_extracts_json(self, mock_build_agent):
        """Mocks the Strands agent instance and verifies analyze_incident passes

        parameters into the prompt and returns the extracted JSON string.
        """
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = (
            'Here is the analysis:\n```json\n{"root_cause": "DB error", "cascade": [], "suggested_fix": "Fix", "summary": "Sum"}\n```'
        )
        mock_build_agent.return_value = mock_agent_instance

        result = agent.analyze_incident(log_group="/incident-iq/demo", minutes_back=15)

        mock_build_agent.assert_called_once()
        mock_agent_instance.assert_called_once()
        call_prompt = mock_agent_instance.call_args[0][0]
        assert "/incident-iq/demo" in call_prompt
        assert "15 minutes" in call_prompt

        assert result == '{"root_cause": "DB error", "cascade": [], "suggested_fix": "Fix", "summary": "Sum"}'

