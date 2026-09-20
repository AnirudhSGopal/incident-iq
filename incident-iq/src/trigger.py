"""
Demo trigger — the single "button press" for the live demo.
Run this to execute the full pipeline end-to-end and print a clean result.

    python src/trigger.py
"""

import json
import sys

import config
from agent import analyze_incident


def main():
    print("Analyzing incident...\n")
    raw_result = analyze_incident(log_group=config.LOG_GROUP)

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
