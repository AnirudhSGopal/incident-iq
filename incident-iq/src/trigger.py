"""
Main CLI for running an end-to-end incident analysis.

Accepts a log group and time window, runs the full analysis pipeline,
and prints a structured, human-readable report to stdout.

Example:
    python src/trigger.py --log-group /incident-iq/demo --minutes-back 15
"""

import argparse
import json
import re
import sys

from agent import analyze_incident

from colorama import init, Fore, Style

# init(autoreset=True) makes every print() automatically reset color
# afterward, so plain content printed after a colored heading doesn't
# inherit the color. Also required on Windows for ANSI colors to
# render correctly in PowerShell / cmd.exe.
init(autoreset=True)


def to_bullets(text):
    """
    Splits a dense paragraph into separate bullet lines.
    Splits on '. ' (sentence boundaries) so each sentence becomes its
    own point, rather than one wall of text.
    """
    if not text:
        return ["N/A"]
    # Split on sentence-ending periods followed by a space/capital letter,
    # keeping the split simple and dependency-free.
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


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
        print(Fore.YELLOW + Style.BRIGHT + "Raw agent output (could not parse as JSON):")
        print(raw_result)
        sys.exit(0)

    print("=" * 60)

    # --- ROOT CAUSE (heading colored, content plain, as bullets) ---
    print(Fore.RED + Style.BRIGHT + "ROOT CAUSE:")
    for point in to_bullets(parsed.get("root_cause", "N/A")):
        print(f"  - {point}")

    print("=" * 60)

    # --- CASCADE (already naturally a list) ---
    print(Fore.YELLOW + Style.BRIGHT + "\nCASCADE:")
    for i, step in enumerate(parsed.get("cascade", []), start=1):
        print(f"  {i}. {step}")

    # --- SUGGESTED FIX (heading colored, content plain, as bullets) ---
    print(Fore.GREEN + Style.BRIGHT + "\nSUGGESTED FIX:")
    for point in to_bullets(parsed.get("suggested_fix", "N/A")):
        print(f"  - {point}")

    # --- SUMMARY (heading colored, content plain, as bullets) ---
    print(Fore.CYAN + Style.BRIGHT + "\nSUMMARY:")
    for point in to_bullets(parsed.get("summary", "N/A")):
        print(f"  - {point}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()