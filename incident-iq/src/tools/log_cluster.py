"""
Strands tool: fetches recent CloudWatch logs and clusters similar error
messages together so the agent receives clean, reduced data instead of
thousands of raw lines.

Test this file standalone BEFORE wiring it into the agent:
    python -c "from src.tools.log_cluster import get_clustered_logs; \
               print(get_clustered_logs())"
"""

import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent src/ directory to the import path so we can import config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boto3
from strands import tool

import config

logs_client = boto3.client("logs", region_name=config.REGION)


def _normalize(message: str) -> str:
    """
    Collapse variable parts (numbers, ids, paths with values) so that
    similar messages cluster together even if small details differ.
    """
    normalized = re.sub(r"\d+", "#", message)
    normalized = re.sub(r"/[a-zA-Z0-9_-]+", "/*", normalized)
    return normalized.strip()


@tool
def get_clustered_logs(log_group: str, minutes_back: int = 10) -> dict:
    """
    Fetch recent logs from a CloudWatch log group and cluster similar error
    messages together with counts and first-seen timestamps, ordered by
    when each cluster first appeared.

    Args:
        log_group: The CloudWatch log group to query.
        minutes_back: How many minutes back to look for logs.

    Returns:
        A dictionary with a "clusters" list, each containing the message
        pattern, occurrence count, and first-seen timestamp (ISO format),
        ordered chronologically by first occurrence.
    """
    if not isinstance(log_group, str) or not log_group.strip():
        raise ValueError("log_group is required")
    if minutes_back > 60:
        raise ValueError(f"minutes_back must be 60 or less, got {minutes_back}")
    if minutes_back <= 0:
        raise ValueError(f"minutes_back must be positive, got {minutes_back}")

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=minutes_back)

    response = logs_client.filter_log_events(
        logGroupName=log_group,
        startTime=int(start_time.timestamp() * 1000),
        endTime=int(end_time.timestamp() * 1000),
        limit=1000,
    )
    events = response.get("events", [])

    if not events:
        return {
            "clusters": [],
            "warning": f"No log events found in {log_group} for the last {minutes_back} minutes. Run generate_incident.py first.",
        }

    clusters = defaultdict(
        lambda: {
            "count": 0,
            "first_seen_ms": None,
            "first_message": "",
            "raw_messages": set(),
            "affected_endpoints": [],
        }
    )

    for event in events:
        key = _normalize(event["message"])
        entry = clusters[key]
        entry["count"] += 1
        msg = event["message"]
        if not entry["first_message"]:
            entry["first_message"] = msg
        entry["raw_messages"].add(msg)
        for ep in re.findall(r"/[a-zA-Z0-9_-]+", msg):
            if ep not in entry["affected_endpoints"]:
                entry["affected_endpoints"].append(ep)
        ts = event["timestamp"]
        if entry["first_seen_ms"] is None or ts < entry["first_seen_ms"]:
            entry["first_seen_ms"] = ts

    ordered = sorted(clusters.values(), key=lambda c: c["first_seen_ms"])

    result = {
        "clusters": [
            {
                "message": c["first_message"],
                "count": c["count"],
                "first_seen": datetime.fromtimestamp(
                    c["first_seen_ms"] / 1000, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "affected_endpoints": c["affected_endpoints"],
            }
            for c in ordered
        ]
    }
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(get_clustered_logs(log_group=config.LOG_GROUP), indent=2))
