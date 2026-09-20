"""
Main CLI for running an end-to-end incident analysis.

Accepts a log group and time window, runs the full analysis pipeline,
and prints a structured, human-readable report to stdout.

Example:
    python src/trigger.py --log-group /incident-iq/demo --minutes-back 15
"""

import argparse
import json
import sys

from agent import analyze_incident


def main():
    parser = argparse.ArgumentParser(description="Analyze CloudWatch logs for a recent incident.")
    parser.add_argument(
        "--log-group",
        required=True,
        help="The CloudWatch log group to analyze (e.g., /incident-iq/demo)",
    )
    parser.add_argument(
        "--minutes-back",
        type=int,
        default=10,
        help="How many minutes back to look for log events (default: 10)",
    )
    args = parser.parse_args()

    print(f"Analyzing incident in {args.log_group} for the last {args.minutes_back} minutes...\n")
    raw_result = analyze_incident(log_group=args.log_group, minutes_back=args.minutes_back)

    try:
        parsed = json.loads(raw_result)
    except (json.JSONDecodeError, TypeError):
        print("Raw agent output (could not parse as JSON):\n")
        print(raw_result)
        sys.exit(0)

    print("=" * 60)
    print("ROOT CAUSE:", parsed.get("root_cause", "N/A"))
    print("=" * 60)
    print("\nCASCADE:")
    for i, step in enumerate(parsed.get("cascade", []), start=1):
        print(f"  {i}. {step}")
    print("\nSUGGESTED FIX:")
    print(" ", parsed.get("suggested_fix", "N/A"))
    print("\nSUMMARY:")
    print(" ", parsed.get("summary", "N/A"))
    print("=" * 60)


if __name__ == "__main__":
    main()