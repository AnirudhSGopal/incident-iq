"""
Tests for src/tools/log_cluster.py.

Mocks boto3 so no real AWS calls are made. Verifies:
 - Correct clustering of the standard incident event data (3 clusters, counts [3,3,4])
 - ClientError from filter_log_events propagates uncaught
 - Empty events returns a warning dict, not fabricated data
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src/ to the import path so tests can import project modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ---------------------------------------------------------------------------
# Fixture data: the standard synthetic incident events (defined here, NOT
# imported from production code — the production fallback has been deleted).
# ---------------------------------------------------------------------------
def _make_incident_events():
    """Build the 10 standard incident log events used for testing."""
    base = datetime(2025, 1, 1, 0, 0, 0)
    raw = [
        (0, "DB connection pool exhausted: max_connections=100 reached"),
        (1, "DB connection pool exhausted: max_connections=100 reached"),
        (2, "DB connection pool exhausted: max_connections=100 reached"),
        (3, "API timeout: /checkout endpoint exceeded 5000ms"),
        (4, "API timeout: /checkout endpoint exceeded 5000ms"),
        (4, "API timeout: /cart endpoint exceeded 5000ms"),
        (6, "502 Bad Gateway from load balancer for /checkout"),
        (6, "502 Bad Gateway from load balancer for /checkout"),
        (7, "502 Bad Gateway from load balancer for /cart"),
        (7, "502 Bad Gateway from load balancer for /cart"),
    ]
    return [
        {
            "timestamp": int((base + timedelta(seconds=offset)).timestamp() * 1000),
            "message": message,
        }
        for offset, message in raw
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetClusteredLogs:
    """Tests for get_clustered_logs with mocked boto3."""

    @patch("tools.log_cluster.logs_client")
    def test_clusters_standard_incident_data(self, mock_client):
        """Given the standard 10 incident events, should return exactly 3
        clusters with counts [3, 3, 4] in chronological order."""
        mock_client.filter_log_events.return_value = {
            "events": _make_incident_events()
        }

        from tools.log_cluster import get_clustered_logs

        result = get_clustered_logs(
            log_group="/incident-iq/demo", minutes_back=10
        )

        assert "clusters" in result
        clusters = result["clusters"]
        assert len(clusters) == 3

        counts = [c["count"] for c in clusters]
        assert counts == [3, 3, 4]

        # Verify chronological order: first_seen timestamps are ascending
        timestamps = [c["first_seen"] for c in clusters]
        assert timestamps == sorted(timestamps)

        # Verify cluster messages match expected patterns
        messages = [c["message"] for c in clusters]
        assert any("DB connection pool" in m for m in messages)
        assert any("API timeout" in m for m in messages)
        assert any("502 Bad Gateway" in m for m in messages)

        # Verify affected endpoints in each cluster
        assert clusters[0]["affected_endpoints"] == []
        assert clusters[1]["affected_endpoints"] == ["/checkout", "/cart"]
        assert clusters[2]["affected_endpoints"] == ["/checkout", "/cart"]

    @patch("tools.log_cluster.logs_client")
    def test_client_error_propagates(self, mock_client):
        """If filter_log_events raises a ClientError, it must NOT be
        swallowed — it should propagate out of get_clustered_logs."""
        from botocore.exceptions import ClientError

        mock_client.filter_log_events.side_effect = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException", "Message": "Log group not found"}},
            operation_name="FilterLogEvents",
        )

        from tools.log_cluster import get_clustered_logs

        with pytest.raises(ClientError):
            get_clustered_logs(log_group="/nonexistent", minutes_back=10)

    @patch("tools.log_cluster.logs_client")
    def test_empty_events_returns_warning(self, mock_client):
        """If filter_log_events succeeds but returns zero events, should
        return {"clusters": [], "warning": ...} — no fabricated data."""
        mock_client.filter_log_events.return_value = {"events": []}

        from tools.log_cluster import get_clustered_logs

        result = get_clustered_logs(
            log_group="/incident-iq/demo", minutes_back=10
        )

        assert result["clusters"] == []
        assert "warning" in result
        assert "No log events found" in result["warning"]
        assert "generate_incident.py" in result["warning"]

    def test_minutes_back_over_cap_raises(self):
        """Calls get_clustered_logs with minutes_back=999 and asserts pytest.raises(ValueError)."""
        from tools.log_cluster import get_clustered_logs

        with pytest.raises(ValueError, match="minutes_back must be 60 or less"):
            get_clustered_logs(log_group="/incident-iq/demo", minutes_back=999)

    def test_minutes_back_zero_or_negative_raises(self):
        """Same pattern for minutes_back=0 and minutes_back=-5."""
        from tools.log_cluster import get_clustered_logs

        with pytest.raises(ValueError, match="minutes_back must be positive"):
            get_clustered_logs(log_group="/incident-iq/demo", minutes_back=0)

        with pytest.raises(ValueError, match="minutes_back must be positive"):
            get_clustered_logs(log_group="/incident-iq/demo", minutes_back=-5)
