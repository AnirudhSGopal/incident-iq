"""
IncidentIQ Project Audit Script

Standalone verification script that makes real AWS and local calls to verify
the entire environment, dependencies, CloudWatch logs, log clustering, and
agent reasoning end-to-end.
"""

import importlib.metadata
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src/ directory to import path
SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))


def extract_json(raw_text: str) -> dict:
    """Extract and parse JSON object from raw agent response text."""
    try:
        return json.loads(raw_text.strip())
    except Exception:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw_text[start : end + 1])

    raise ValueError(f"Could not extract valid JSON from response:\n{raw_text}")


def main():
    print("=" * 70)
    print("IncidentIQ - Environment & Pipeline Real Audit")
    print("=" * 70)

    results = []

    # -------------------------------------------------------------------------
    # Check 1: Required Packages Installed
    # -------------------------------------------------------------------------
    print("\n[Check 1/6] Verifying required packages...")
    packages = ["strands-agents", "strands-agents-tools", "boto3", "pytest"]
    pkg_details = []
    check1_passed = True

    for pkg in packages:
        try:
            version = importlib.metadata.version(pkg)
            pkg_details.append(f"{pkg}=={version}")
            print(f"  - {pkg}: {version}")
        except importlib.metadata.PackageNotFoundError:
            pkg_details.append(f"{pkg} (MISSING)")
            print(f"  - {pkg}: NOT INSTALLED")
            check1_passed = False
        except Exception as e:
            pkg_details.append(f"{pkg} ({e})")
            print(f"  - {pkg}: ERROR ({e})")
            check1_passed = False

    if check1_passed:
        results.append((1, "Installed Packages", "PASS", ", ".join(pkg_details)))
    else:
        results.append((1, "Installed Packages", "FAIL", ", ".join(pkg_details)))

    # -------------------------------------------------------------------------
    # Check 2: AWS Credentials & STS Caller Identity
    # -------------------------------------------------------------------------
    print("\n[Check 2/6] Verifying AWS Credentials (STS get_caller_identity)...")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        import boto3
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        arn = identity.get("Arn", "")
        print(f"  - STS Caller Arn: {arn}")
        results.append((2, "AWS STS Credentials", "PASS", f"Arn: {arn}"))
    except Exception as e:
        print(f"  - STS call failed: {e}")
        results.append((2, "AWS STS Credentials", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # Check 3: Bedrock Foundation Models (Claude access)
    # -------------------------------------------------------------------------
    print("\n[Check 3/6] Verifying Bedrock Claude models (us-west-2)...")
    try:
        bedrock = boto3.client("bedrock", region_name="us-west-2")
        models_resp = bedrock.list_foundation_models()
        claude_models = [
            m["modelId"]
            for m in models_resp.get("modelSummaries", [])
            if "claude" in m.get("modelId", "").lower()
        ]
        if claude_models:
            print(f"  - Found {len(claude_models)} Claude models (e.g. {claude_models[0]})")
            results.append((3, "Bedrock Claude Models", "PASS", f"{len(claude_models)} Claude models available"))
        else:
            print("  - No Claude foundation models found.")
            results.append((3, "Bedrock Claude Models", "FAIL", "No Claude model IDs found in Bedrock"))
    except Exception as e:
        print(f"  - Bedrock call failed: {e}")
        results.append((3, "Bedrock Claude Models", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # Check 4: CloudWatch Logs (last 30 minutes)
    # -------------------------------------------------------------------------
    print("\n[Check 4/6] Verifying CloudWatch log events (last 30 minutes)...")
    try:
        import config
        logs_client = boto3.client("logs", region_name="us-west-2")
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=30)
        cw_resp = logs_client.filter_log_events(
            logGroupName=config.LOG_GROUP,
            startTime=int(start_time.timestamp() * 1000),
            endTime=int(end_time.timestamp() * 1000),
        )
        events = cw_resp.get("events", [])
        num_events = len(events)
        print(f"  - Log group: {config.LOG_GROUP}")
        print(f"  - Found: {num_events} events")

        if num_events > 0:
            results.append((4, "CloudWatch Log Query", "PASS", f"{num_events} events in last 30m"))
        else:
            print("  - [Hint] Run generate_incident.py first to seed log events.")
            results.append((4, "CloudWatch Log Query", "WARN", "0 events found (run generate_incident.py first)"))
    except Exception as e:
        print(f"  - CloudWatch logs call failed: {e}")
        results.append((4, "CloudWatch Log Query", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # Check 5: get_clustered_logs tool verification
    # -------------------------------------------------------------------------
    print("\n[Check 5/6] Verifying get_clustered_logs() output & clustering...")
    try:
        from tools.log_cluster import get_clustered_logs
        cluster_result = get_clustered_logs(log_group=config.LOG_GROUP)
        clusters = cluster_result.get("clusters", [])
        counts = [c.get("count") for c in clusters]
        timestamps = [c.get("first_seen") for c in clusters]

        is_chrono = timestamps == sorted(timestamps)
        has_3_clusters = len(clusters) == 3
        has_expected_counts = counts == [3, 3, 4]

        if has_3_clusters and has_expected_counts and is_chrono:
            print(f"  - Returned 3 clusters with counts {counts} in chronological order.")
            results.append((5, "Log Clustering Tool", "PASS", f"3 clusters, counts {counts}, chronologically ordered"))
        else:
            detail = f"clusters={len(clusters)}, counts={counts}, chronological={is_chrono}"
            print(f"  - Clustering check failed: {detail}")
            print(f"  - Actual clusters: {json.dumps(clusters, indent=2)}")
            results.append((5, "Log Clustering Tool", "FAIL", detail))
    except Exception as e:
        print(f"  - get_clustered_logs call failed: {e}")
        results.append((5, "Log Clustering Tool", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # Check 6: analyze_incident() agent execution
    # -------------------------------------------------------------------------
    print("\n[Check 6/6] Verifying analyze_incident() real agent execution...")
    try:
        from agent import analyze_incident
        raw_agent_response = analyze_incident(log_group=config.LOG_GROUP)
        parsed = extract_json(raw_agent_response)

        required_keys = ["root_cause", "cascade", "suggested_fix", "summary"]
        missing_keys = [k for k in required_keys if k not in parsed]

        root_cause = str(parsed.get("root_cause", "")).lower()
        root_cause_keywords = ["pool", "db", "database", "connection"]
        has_keyword = any(kw in root_cause for kw in root_cause_keywords)

        if not missing_keys and has_keyword:
            print("  - Agent response valid JSON with all 4 keys.")
            print(f"  - Root cause mentions expected DB connection keywords: \"{parsed.get('root_cause')}\"")
            results.append((6, "Agent Root Cause Analysis", "PASS", "All 4 keys present; root_cause mentions DB connection pool"))
        else:
            failure_reasons = []
            if missing_keys:
                failure_reasons.append(f"Missing keys: {missing_keys}")
            if not has_keyword:
                failure_reasons.append(f"root_cause did not mention any of {root_cause_keywords}: '{parsed.get('root_cause')}'")
            detail = "; ".join(failure_reasons)
            print(f"  - Agent check failed: {detail}")
            print(f"  - Actual parsed output: {json.dumps(parsed, indent=2)}")
            results.append((6, "Agent Root Cause Analysis", "FAIL", detail))
    except Exception as e:
        print(f"  - analyze_incident execution failed: {e}")
        results.append((6, "Agent Root Cause Analysis", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # Final Summary Table
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("AUDIT SUMMARY TABLE")
    print("=" * 70)
    print(f"{'#':<3} | {'Check':<27} | {'Status':<6} | {'Details'}")
    print("-" * 70)

    any_fail = False
    for num, name, status, details in results:
        if status == "FAIL":
            any_fail = True
        # Truncate details if overly long for clean table formatting
        short_details = details if len(details) <= 60 else details[:57] + "..."
        print(f"{num:<3} | {name:<27} | {status:<6} | {short_details}")

    print("=" * 70)

    # State plainly whether demoable
    if any_fail:
        print("\nDEMOABLE: NO\n")
        sys.exit(1)
    else:
        print("\nDEMOABLE: YES\n")
        sys.exit(0)


if __name__ == "__main__":
    main()

