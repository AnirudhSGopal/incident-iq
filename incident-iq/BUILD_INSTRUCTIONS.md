# BUILD_INSTRUCTIONS.md

**How to use this file:** Paste this entire document as one message into Claude Code
or Kiro inside your sandbox. It contains every file, in full, with an explanation of
what each one does and why, in the exact order they must be created and tested. Tell
your AI tool: *"Follow this document exactly, creating each file in order, and running
the verification command after each step before moving to the next."*

---

## 0. Before anything: environment check

Run these first. Do not proceed until all three succeed.

```bash
aws sts get-caller-identity
aws configure get region
pip install -r requirements.txt
```

`requirements.txt`:
```
strands-agents
strands-agents-tools
boto3
```

**Why:** if credentials, region, or packages aren't right, every later step fails in
confusing ways that look like bugs in the code but aren't. Ruling this out first saves
the most time in an 8-hour window.

Also confirm in the AWS Console: **Bedrock → Model access → Claude is enabled** in the
region printed by `aws configure get region`. If it says a different region than
`us-west-2`, change every `REGION = "us-west-2"` line below to match.

---

## 1. File: `src/generate_incident.py`

**What it does:** Writes a fake, timestamped, cascading-failure incident into
CloudWatch Logs, so the rest of the pipeline has reliable data to work with instead of
needing a real production system.

**Why this shape:** three error types in a clear time order (DB pool exhaustion → API
timeouts → 502 errors) so there's an unambiguous "correct answer" you can check the
agent's reasoning against later.

```python
"""
Seeds a realistic, timestamped, cascading-failure incident into CloudWatch Logs.
Run this FIRST. Verify in the CloudWatch console that /incident-iq/demo contains
these lines before moving to step 2.
"""

import boto3
from datetime import datetime, timedelta

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


def push_synthetic_incident():
    base = datetime.utcnow()
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
    logs.put_log_events(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM, logEvents=log_events)
    print(f"Pushed {len(log_events)} synthetic log events to {LOG_GROUP}/{LOG_STREAM}")


if __name__ == "__main__":
    ensure_log_group_and_stream()
    push_synthetic_incident()
    print("\nDone. Verify in the CloudWatch console before moving to step 2.")
```

**Verify:** `python src/generate_incident.py`, then check the AWS Console → CloudWatch
→ Log groups → `/incident-iq/demo` → confirm 10 log lines are there. Do not proceed
until you see them.

---

## 2. File: `src/tools/log_cluster.py`

**What it does:** Fetches the raw logs just written and groups similar ones together,
so instead of handing the AI agent 10+ raw lines (or thousands, in a real system), it
gets 3 clean clusters with counts and first-seen times. This is a Strands `@tool` —
a Python function the agent can call on its own.

**Why this matters:** never feed raw, unclustered logs directly to an LLM — it's
expensive, slow, and the model reasons better over a small, clean summary than a wall
of near-duplicate text.

```python
"""
Strands tool: fetches recent CloudWatch logs and clusters similar error
messages together. Test standalone BEFORE wiring into the agent:
    python -m src.tools.log_cluster
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta

import boto3
from strands import tool

REGION = "us-west-2"  # must match generate_incident.py
logs_client = boto3.client("logs", region_name=REGION)


def _normalize(message: str) -> str:
    """Collapse numbers so similar messages cluster even with small differences."""
    return re.sub(r"\d+", "#", message).strip()


@tool
def get_clustered_logs(log_group: str = "/incident-iq/demo", minutes_back: int = 10) -> dict:
    """
    Fetch recent logs from a CloudWatch log group and cluster similar error
    messages together with counts and first-seen timestamps, ordered
    chronologically by first occurrence.

    Args:
        log_group: The CloudWatch log group to query.
        minutes_back: How many minutes back to look for logs.

    Returns:
        A dict with a "clusters" list: message, count, first_seen (ISO format).
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=minutes_back)

    response = logs_client.filter_log_events(
        logGroupName=log_group,
        startTime=int(start_time.timestamp() * 1000),
        endTime=int(end_time.timestamp() * 1000),
    )

    clusters = defaultdict(lambda: {"count": 0, "first_seen_ms": None, "example": ""})
    for event in response.get("events", []):
        key = _normalize(event["message"])
        entry = clusters[key]
        entry["count"] += 1
        entry["example"] = event["message"]
        ts = event["timestamp"]
        if entry["first_seen_ms"] is None or ts < entry["first_seen_ms"]:
            entry["first_seen_ms"] = ts

    ordered = sorted(clusters.values(), key=lambda c: c["first_seen_ms"])
    return {
        "clusters": [
            {
                "message": c["example"],
                "count": c["count"],
                "first_seen": datetime.utcfromtimestamp(c["first_seen_ms"] / 1000).isoformat() + "Z",
            }
            for c in ordered
        ]
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_clustered_logs(), indent=2))
```

**Verify:** `python -m src.tools.log_cluster` — you should see exactly 3 clusters
(DB pool, API timeout, 502) with counts of 3, 3, and 4 respectively, in that order.
If the order or counts look wrong, fix this file before moving on — do not proceed
to the agent with broken clustering.

---

## 3. File: `prompts/system_prompt.md`

**What it does:** This is the agent's entire reasoning instruction — the most
important file in the project. If the agent's answers are ever wrong or vague, this
is the file to edit, not the Python code.

```markdown
# IncidentIQ Agent — System Prompt

You are IncidentIQ, an expert Site Reliability Engineer AI assistant. You are given
clustered error data from a production incident. Each cluster represents a group of
similar log messages, with a count of occurrences and the timestamp it was first seen.

Your job is to reason about the clusters in chronological order and determine:

1. **Root cause** — which cluster represents the *original* failure, not a downstream
   symptom. The earliest timestamp is a strong signal, but reason about plausibility too:
   a database or resource-exhaustion failure is more often a root cause than a generic
   HTTP error, which is more often a symptom.
2. **Cascade** — list the remaining clusters in the order they likely occurred *as a
   consequence* of the root cause. Briefly state the causal link between each step.
3. **Suggested fix** — one concrete, actionable next step an engineer could take right
   now to address the root cause (not just the symptoms).
4. **Summary** — a 2-3 sentence plain-English explanation suitable for a postmortem,
   written for someone who has not seen the logs.

## Rules

- Always reason from the data given. Do not invent services, error types, or timestamps
  that are not present in the input.
- If the clusters do not clearly imply a single root cause, say so honestly in the
  summary rather than guessing with false confidence.
- Be concise. Engineers reading this during an active incident do not want a long essay.
- Always respond with ONLY a JSON object in the following shape — no preamble, no
  markdown code fences, no extra commentary outside the JSON:

\`\`\`json
{
  "root_cause": "string",
  "cascade": ["string", "string"],
  "suggested_fix": "string",
  "summary": "string"
}
\`\`\`

## Example

Input clusters:
- "DB connection pool exhausted" — count 3, first seen 10:02:00
- "API timeout: /checkout" — count 2, first seen 10:02:03
- "502 Bad Gateway from load balancer" — count 4, first seen 10:02:06

Expected output:
\`\`\`json
{
  "root_cause": "Database connection pool exhausted at 10:02:00, preventing new queries from completing.",
  "cascade": [
    "API requests to /checkout began timing out at 10:02:03 because they were waiting on unavailable DB connections.",
    "The load balancer started returning 502 Bad Gateway errors at 10:02:06 once backend requests failed to respond in time."
  ],
  "suggested_fix": "Increase the DB connection pool size or investigate a recent deploy/query change that increased connection usage, and add query timeouts to fail fast instead of holding connections open.",
  "summary": "The incident originated from DB connection pool exhaustion, which caused API timeouts on checkout and cart endpoints, which in turn caused the load balancer to return 502 errors to end users. The fix should target connection pool capacity and query efficiency, not the symptoms downstream."
}
\`\`\`
```

**Verify:** just save the file — nothing to run yet. It's used by step 4.

---

## 4. File: `src/agent.py`

**What it does:** Defines the actual Strands agent — connects the system prompt above
with the clustering tool from step 2, so the agent can call the tool itself and reason
over what it gets back.

```python
"""
IncidentIQ Strands agent definition.
Run standalone first (before AgentCore deployment): python src/agent.py
"""

from pathlib import Path
from strands import Agent

from tools.log_cluster import get_clustered_logs

SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.md"


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text()


def build_agent() -> Agent:
    return Agent(
        system_prompt=load_system_prompt(),
        tools=[get_clustered_logs],
    )


def analyze_incident(log_group: str = "/incident-iq/demo", minutes_back: int = 10) -> str:
    agent = build_agent()
    prompt = (
        f"Analyze the current incident. Use your tool to fetch clustered logs "
        f"from log group '{log_group}' for the last {minutes_back} minutes, "
        f"then respond with the required JSON output."
    )
    response = agent(prompt)
    return str(response)


if __name__ == "__main__":
    result = analyze_incident()
    print(result)
```

**Verify:** `python src/agent.py` — you should see JSON output identifying DB pool
exhaustion as the root cause, API timeouts and 502s as the cascade, and a sensible
fix. **If this step works, you already have a demoable project**, even before
deployment or a frontend. Do not skip verifying this before moving on.

---

## 5. File: `src/trigger.py`

**What it does:** The actual "button press" for your live demo — runs the full
pipeline and prints a clean, formatted result instead of raw JSON.

```python
"""
Demo trigger — the single "button press" for the live demo.
Run: python src/trigger.py
"""

import json
import sys

from agent import analyze_incident


def main():
    print("Analyzing incident...\n")
    raw_result = analyze_incident()

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
```

**Verify:** `python src/trigger.py` from inside `src/` (or adjust the import if run
from project root) — confirm the formatted output prints cleanly. This is what you
show live in the demo.

---

## 6. File: `frontend/index.html` (optional — skip if using CLI-only demo)

**What it does:** A single-button web page alternative to the CLI, for a more visual
demo. Requires an HTTP endpoint in front of your agent (e.g., AgentCore's endpoint, or
a small Lambda + API Gateway wrapper) — set `AGENT_ENDPOINT` before using this.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>IncidentIQ</title>
<style>
  :root { --bg:#0b0f14; --panel:#131a22; --accent:#ff5c5c; --text:#e6edf3; --muted:#8b98a5; }
  body { background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; max-width:720px; margin:40px auto; padding:0 20px; }
  h1 { font-size:1.6rem; }
  p.tagline { color:var(--muted); margin-top:-8px; }
  button { background:var(--accent); color:white; border:none; padding:14px 24px; font-size:1rem; border-radius:8px; cursor:pointer; margin:20px 0; }
  button:disabled { opacity:0.6; cursor:default; }
  .panel { background:var(--panel); border-radius:10px; padding:20px; margin-top:16px; white-space:pre-wrap; line-height:1.5; }
  .label { color:var(--accent); font-weight:600; }
</style>
</head>
<body>
  <h1>IncidentIQ</h1>
  <p class="tagline">Turns messy production logs into a root-cause answer in seconds.</p>
  <button id="analyzeBtn" onclick="analyze()">Analyze Incident</button>
  <div class="panel" id="output">Click "Analyze Incident" to run the demo.</div>
  <script>
    const AGENT_ENDPOINT = "REPLACE_WITH_YOUR_AGENTCORE_OR_API_ENDPOINT";
    async function analyze() {
      const btn = document.getElementById("analyzeBtn");
      const out = document.getElementById("output");
      btn.disabled = true;
      out.textContent = "Analyzing...";
      try {
        const res = await fetch(AGENT_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ log_group: "/incident-iq/demo", minutes_back: 10 }),
        });
        const data = await res.json();
        out.innerHTML =
          `<span class="label">ROOT CAUSE:</span>\n${data.root_cause}\n\n` +
          `<span class="label">CASCADE:</span>\n${(data.cascade || []).map((c,i)=>`${i+1}. ${c}`).join("\n")}\n\n` +
          `<span class="label">SUGGESTED FIX:</span>\n${data.suggested_fix}\n\n` +
          `<span class="label">SUMMARY:</span>\n${data.summary}`;
      } catch (err) {
        out.textContent = "Error calling agent: " + err.message +
          "\n\n(Fallback: run 'python src/trigger.py' in your terminal for the local demo.)";
      } finally {
        btn.disabled = false;
      }
    }
  </script>
</body>
</html>
```

**Verify:** open in a browser, click the button. If `AGENT_ENDPOINT` isn't set yet,
this will error — that's expected until deployment (step 7) is done.

---

## 7. AgentCore deployment (stretch goal — only after steps 1–5 all pass)

This step is intentionally described rather than scripted, because deployment
commands depend on the exact AgentCore CLI/tooling available in your specific
sandbox. Ask Claude Code or Kiro directly at this point:

```
I have a working local Strands agent in src/agent.py that passes locally. Show me
the exact commands to package and deploy this to Amazon Bedrock AgentCore Runtime
in this sandbox, and how to get an invocable HTTPS endpoint back.
```

**If this step stalls or errors and you're running low on time: stop and use the
local agent (steps 1–5) for your demo.** That is a complete, legitimate, working
project on its own.

---

## Order of operations summary

1. Environment check → 2. `generate_incident.py` (verify in console) → 3.
`log_cluster.py` (verify output standalone) → 4. `system_prompt.md` (just save) → 5.
`agent.py` (verify JSON output is correct) → 6. `trigger.py` (verify clean formatted
output) → 7. optional frontend → 8. optional AgentCore deployment.

**Never skip a verification step. Each one exists because it catches a specific class
of error before it compounds into the next file.**
