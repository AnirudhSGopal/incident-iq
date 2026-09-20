"""
Seeds a realistic, timestamped, cascading-failure incident into CloudWatch Logs
so the rest of the pipeline has reliable, repeatable data to work with.

Run this FIRST, before anything else. Verify in the CloudWatch console that
the log group /incident-iq/demo contains these lines before moving on.
"""

import boto3
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

REGION = "us-west-2"  # change if your sandbox uses a different region
LOG_GROUP = "/incident-iq/demo"
LOG_STREAM = "incident-001"

logs = boto3.client("logs", region_name=REGION)


def ensure_log_group_and_stream():
    try:
        logs.create_log_group(logGroupName=LOG_GROUP)
        print(f"Created log group {LOG_GROUP}")
    except logs.exceptions.ResourceAlreadyExistsException:
        print(f"Log group {LOG_GROUP} already exists")

    try:
        logs.create_log_stream(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM)
        print(f"Created log stream {LOG_STREAM}")
    except logs.exceptions.ResourceAlreadyExistsException:
        print(f"Log stream {LOG_STREAM} already exists")


def push_db_pool_incident():
    """
    Simulates: DB connection pool exhaustion -> API timeouts -> 502s from load balancer.
    Offsets are in seconds from 'now' so the incident always looks recent.
    """
    base = datetime.now(timezone.utc)

    events = [
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

    log_events = [
        {
            "timestamp": int((base + timedelta(seconds=offset)).timestamp() * 1000),
            "message": message,
        }
        for offset, message in events
    ]

    logs.put_log_events(
        logGroupName=LOG_GROUP,
        logStreamName=LOG_STREAM,
        logEvents=log_events,
    )
    print(f"Pushed {len(log_events)} synthetic log events to {LOG_GROUP}/{LOG_STREAM}")


def push_memory_leak_incident():
    """
    Simulates: Gradual memory pressure -> OutOfMemoryError -> Service restarted by health check.
    Events are spaced over several minutes to reflect a slower leak progression.
    """
    base = datetime.now(timezone.utc)

    events = [
        (-480, "High memory usage: 85% of heap used"),
        (-360, "High memory usage: 92% of heap used"),
        (-300, "High memory usage: 97% of heap used"),
        (-180, "OutOfMemoryError: Java heap space"),
        (-170, "OutOfMemoryError: Java heap space"),
        (-160, "OutOfMemoryError: Java heap space"),
        (-60, "Service restarted by health check"),
        (-30, "Service restarted by health check"),
    ]

    log_events = [
        {
            "timestamp": int((base + timedelta(seconds=offset)).timestamp() * 1000),
            "message": message,
        }
        for offset, message in events
    ]

    logs.put_log_events(
        logGroupName=LOG_GROUP,
        logStreamName=LOG_STREAM,
        logEvents=log_events,
    )
    print(f"Pushed {len(log_events)} synthetic memory leak log events to {LOG_GROUP}/{LOG_STREAM}")


if __name__ == "__main__":
    import argparse
    from botocore.exceptions import NoCredentialsError

    parser = argparse.ArgumentParser(description="Seed synthetic incident logs to CloudWatch")
    parser.add_argument(
        "--scenario",
        choices=["db_pool", "memory_leak"],
        default="db_pool",
        help="Incident scenario to seed: db_pool (default) or memory_leak",
    )
    args = parser.parse_args()

    try:
        ensure_log_group_and_stream()
        if args.scenario == "memory_leak":
            push_memory_leak_incident()
        else:
            push_db_pool_incident()
        print("\nDone. Verify in the CloudWatch console before moving to the next step.")
    except NoCredentialsError:
        print("\n[Notice] No AWS credentials found.")
        print("To push synthetic incident logs directly to AWS CloudWatch, configure your AWS credentials:")
        print("  $env:AWS_ACCESS_KEY_ID='your_access_key'")
        print("  $env:AWS_SECRET_ACCESS_KEY='your_secret_key'")
        print("  $env:AWS_DEFAULT_REGION='us-west-2'")
        print("Local demo and testing mode will continue to use synthetic incident data automatically.")