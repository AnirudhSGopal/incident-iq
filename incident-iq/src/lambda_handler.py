"""
IncidentIQ Lambda handler.

Parses the API Gateway POST /analyze event body for:
  - log_group  (str, required) — returns 400 if missing
  - minutes_back (int, optional, default 10)

Calls analyze_incident(), persists the result to DynamoDB with a UUID
incident_id and UTC timestamp, then returns a proper HTTP response with
CORS headers.

On any failure inside analyze_incident() a real 500 is returned with the
actual exception message — no fabricated fallback data.
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Make sure the src/ directory is on the path so sibling imports work
# both locally and inside the Lambda execution environment.
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent import analyze_incident  # noqa: E402 — must come after sys.path fix

# ---------------------------------------------------------------------------
# AWS clients (initialised once at cold-start)
# ---------------------------------------------------------------------------
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "IncidentIQHistory")
_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(TABLE_NAME)

# ---------------------------------------------------------------------------
# CORS headers included on every response
# ---------------------------------------------------------------------------
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}


def _response(status_code: int, body: dict) -> dict:
    """Build a well-formed API Gateway Lambda proxy response."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def handler(event: dict, context) -> dict:
    """
    Main Lambda entry point.

    Expected request body (JSON):
        {
            "log_group": "/my/cloudwatch/log-group",   # required
            "minutes_back": 10                          # optional
        }

    Returns:
        200  — successful analysis result + incident_id
        400  — log_group missing from request body
        500  — any exception raised by analyze_incident()
    """
    # ── 1. Parse request body ────────────────────────────────────────────────
    raw_body = event.get("body") or "{}"
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        return _response(400, {"error": "Request body must be valid JSON."})

    log_group: str = body.get("log_group", "").strip()
    if not log_group:
        logger.warning("Missing required field: log_group is missing or empty.")
        return _response(
            400,
            {"error": "log_group is required. Pass it in the JSON request body."},
        )

    minutes_back: int = int(body.get("minutes_back", 10))
    logger.info(
        "Starting incident analysis for log_group='%s' (minutes_back=%d)",
        log_group,
        minutes_back,
    )

    # ── 2. Run the analysis pipeline ─────────────────────────────────────────
    try:
        analysis_result = analyze_incident(
            log_group=log_group,
            minutes_back=minutes_back,
        )
    except Exception as exc:
        # Return the real error — no invented fallback data
        logger.error(
            "analyze_incident() raised an exception: %s",
            exc,
            exc_info=True,
        )
        return _response(
            500,
            {
                "error": "analyze_incident() raised an exception.",
                "detail": str(exc),
            },
        )

    # ── 3. Persist to DynamoDB ────────────────────────────────────────────────
    incident_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    _table.put_item(
        Item={
            "incident_id": incident_id,
            "timestamp": timestamp,
            "log_group": log_group,
            "minutes_back": minutes_back,
            "result": analysis_result,
        }
    )

    # ── 4. Return success response ────────────────────────────────────────────
    root_cause = str(
        analysis_result.get("root_cause", "")
        if isinstance(analysis_result, dict)
        else ""
    )[:100]
    logger.info(
        "Analysis completed successfully: incident_id=%s, root_cause='%s'",
        incident_id,
        root_cause,
    )

    return _response(
        200,
        {
            "incident_id": incident_id,
            "timestamp": timestamp,
            "log_group": log_group,
            "minutes_back": minutes_back,
            "result": analysis_result,
        },
    )

