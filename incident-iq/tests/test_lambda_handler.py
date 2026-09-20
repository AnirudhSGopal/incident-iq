"""
Tests for src/lambda_handler.py.

Mocks boto3 and analyze_incident so no real AWS calls or LLM inferences
are made. Verifies:
 - Valid request returns HTTP 200 with structured analysis payload
 - Missing log_group returns HTTP 400 with a clear error message
 - Exceptions inside analyze_incident return HTTP 500 with real error details
 - Successful requests write the expected record to DynamoDB exactly once
"""

import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure default AWS region is configured before boto3 initializes clients
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
os.environ.setdefault("DYNAMODB_TABLE", "IncidentIQHistory")

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import lambda_handler


# ---------------------------------------------------------------------------
# Fixtures & sample data
# ---------------------------------------------------------------------------
SAMPLE_ANALYSIS_RESULT = {
    "root_cause": "Database connection pool exhausted: max_connections=100 reached",
    "cascade": [
        "Payment service raised connection timeout",
        "Order checkout API returned 502 Bad Gateway",
        "Frontend displayed order processing failure",
    ],
    "suggested_fix": "Increase DB connection pool limit to 300 and add pool backpressure.",
    "summary": "Database connection exhaustion cascaded to checkout 502 failures.",
}


def _make_event(body: dict | None = None, raw_body: str | None = None) -> dict:
    """Helper to construct an API Gateway Lambda proxy integration event."""
    if raw_body is not None:
        return {"body": raw_body}
    if body is not None:
        return {"body": json.dumps(body)}
    return {"body": "{}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestLambdaHandler:
    """Unit tests for the IncidentIQ Lambda entrypoint."""

    @patch("lambda_handler._table")
    @patch("lambda_handler.analyze_incident")
    def test_valid_request_returns_200(self, mock_analyze, mock_table, caplog):
        """Mocks analyze_incident to return a valid result matching the real shape

        (root_cause, cascade, suggested_fix, summary). Calls the handler with
        a valid event body containing log_group, asserts statusCode == 200,
        and asserts the parsed body contains incident_id, timestamp, log_group,
        minutes_back, and result with the correct nested keys.
        Also asserts INFO logs for request start and successful completion.
        """
        mock_analyze.return_value = SAMPLE_ANALYSIS_RESULT

        event = _make_event(
            body={"log_group": "/incident-iq/demo", "minutes_back": 15}
        )
        with caplog.at_level(logging.INFO):
            response = lambda_handler.handler(event, None)

        assert response["statusCode"] == 200
        assert "headers" in response
        assert response["headers"]["Content-Type"] == "application/json"

        body = json.loads(response["body"])

        # Top-level required keys
        assert "incident_id" in body and isinstance(body["incident_id"], str)
        assert "timestamp" in body and isinstance(body["timestamp"], str)
        assert body["log_group"] == "/incident-iq/demo"
        assert body["minutes_back"] == 15

        # Nested analysis result structure
        assert "result" in body
        result = body["result"]
        assert result["root_cause"] == SAMPLE_ANALYSIS_RESULT["root_cause"]
        assert result["cascade"] == SAMPLE_ANALYSIS_RESULT["cascade"]
        assert result["suggested_fix"] == SAMPLE_ANALYSIS_RESULT["suggested_fix"]
        assert result["summary"] == SAMPLE_ANALYSIS_RESULT["summary"]

        mock_analyze.assert_called_once_with(
            log_group="/incident-iq/demo",
            minutes_back=15,
        )

        # Verify structured logging at INFO level
        info_records = [r for r in caplog.records if r.levelname == "INFO"]
        assert any("Starting incident analysis" in r.message and "/incident-iq/demo" in r.message for r in info_records)
        assert any("Analysis completed successfully" in r.message and body["incident_id"] in r.message for r in info_records)

    def test_missing_log_group_returns_400(self, caplog):
        """Calls the handler with an event body missing log_group, asserts

        statusCode == 400, asserts the body contains a clear error message,
        and asserts a WARNING log is recorded.
        """
        event = _make_event(body={"minutes_back": 10})
        with caplog.at_level(logging.WARNING):
            response = lambda_handler.handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "log_group is required" in body["error"]

        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("log_group is missing" in r.message for r in warning_records)

    @patch("lambda_handler.analyze_incident")
    def test_exception_in_analyze_incident_returns_500(self, mock_analyze, caplog):
        """Mocks analyze_incident to raise an exception, calls the handler,

        asserts statusCode == 500, asserts the real exception message
        appears in the response body (not fabricated fallback data),
        and asserts an ERROR log with exc_info is recorded.
        """
        error_message = "Bedrock ModelTimeoutException: Request timed out after 30s"
        mock_analyze.side_effect = RuntimeError(error_message)

        event = _make_event(body={"log_group": "/incident-iq/demo"})
        with caplog.at_level(logging.ERROR):
            response = lambda_handler.handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body
        assert "analyze_incident() raised an exception" in body["error"]
        assert body["detail"] == error_message

        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert any("analyze_incident() raised an exception" in r.message for r in error_records)
        assert any(r.exc_info is not None for r in error_records)

    @patch("lambda_handler._table")
    @patch("lambda_handler.analyze_incident")
    def test_successful_request_writes_to_dynamodb(self, mock_analyze, mock_table):
        """Mocks the DynamoDB resource/table, calls the handler with a valid request,

        asserts put_item was called exactly once, and asserts the item passed to
        put_item contains the correct table reference and an incident_id key.
        """
        mock_analyze.return_value = SAMPLE_ANALYSIS_RESULT

        event = _make_event(body={"log_group": "/incident-iq/demo", "minutes_back": 10})
        response = lambda_handler.handler(event, None)

        assert response["statusCode"] == 200

        # Assert table reference matches configured DynamoDB table
        assert lambda_handler.TABLE_NAME == "IncidentIQHistory"

        # Assert put_item was called exactly once
        mock_table.put_item.assert_called_once()

        # Extract Item passed to put_item
        call_kwargs = mock_table.put_item.call_args.kwargs
        assert "Item" in call_kwargs
        item = call_kwargs["Item"]

        assert "incident_id" in item and len(item["incident_id"]) > 0
        assert "timestamp" in item
        assert item["log_group"] == "/incident-iq/demo"
        assert item["minutes_back"] == 10
        assert item["result"] == SAMPLE_ANALYSIS_RESULT

