---
name: incident-analysis
description: Use this skill whenever the user asks to analyze a production incident, diagnose a root cause from logs, or run/extend the IncidentIQ agent. Covers fetching clustered CloudWatch logs, reasoning about root cause and cascade order, generating the structured JSON output, and deploying/testing the Strands agent on Bedrock AgentCore. Trigger on phrases like "analyze the incident", "run IncidentIQ", "find the root cause", "why did the demo logs fail", or any request to modify the clustering tool, agent prompt, or deployment for this project.
---

# Incident Analysis Skill

This skill packages everything needed to build, run, and extend IncidentIQ — an agent
that turns clustered production log data into a root-cause diagnosis.

## When to use this skill
- The user asks to analyze logs or diagnose an incident for this project
- The user asks to add/modify a tool the agent uses
- The user asks to change the agent's reasoning behavior or output shape
- The user asks to deploy or redeploy the agent to AgentCore
- The user asks to seed new synthetic incident scenarios for testing/demo

## Required context (read before acting)
1. `prompts/system_prompt.md` — the exact reasoning contract the agent must follow.
   Any change to agent behavior starts by editing this file, not by improvising in code.
2. `src/tools/log_cluster.py` — the only data the agent is allowed to reason over is
   what this tool returns. Never hand the agent raw, unclustered log lines.
3. `CLAUDE.md` / `.kiro/steering/project.md` — build order and project-wide constraints.

## Output contract (never deviate without updating system_prompt.md too)
```json
{
  "root_cause": "string",
  "cascade": ["string", "..."],
  "suggested_fix": "string",
  "summary": "string"
}
```

## Standard workflow this skill follows

1. **Seed or confirm data exists**
   Run `src/generate_incident.py` if the log group `/incident-iq/demo` is empty or the
   user wants a fresh/different scenario. Verify by re-reading the clustered output
   before proceeding — never assume logs are present.

2. **Test the clustering tool in isolation**
   `python -m src.tools.log_cluster` (or call `get_clustered_logs()` directly).
   Confirm the returned clusters are sensible (distinct messages, correct counts,
   chronological first-seen order) before touching the agent.

3. **Run the agent locally**
   `python src/agent.py`. Confirm the JSON output matches the contract above and that
   the root cause is the earliest, most plausible originating failure — not just the
   first line alphabetically or the loudest (highest-count) cluster.

4. **Only then consider AgentCore deployment**
   Do not deploy before step 3 passes. Deployment issues are easy to mistake for
   reasoning issues if done out of order — isolate them.

5. **Surface results via `src/trigger.py` or `frontend/index.html`**
   These are thin wrappers. Do not add business logic here — if the output looks wrong,
   fix `system_prompt.md` or `log_cluster.py`, not the trigger/frontend layer.

## Guardrails specific to this skill
- Never fabricate log content, service names, or timestamps not present in the actual
  clustered data — this applies both to the agent's output and to any synthetic data
  you generate for testing.
- Keep the demo scenario singular and reliable unless explicitly asked to add more —
  extra scenarios add risk without adding score in a time-boxed hackathon.
- If asked to add a new tool (e.g., a second data source), follow the same `@tool`
  pattern used in `log_cluster.py` and register it alongside the existing tool in
  `agent.py`'s `tools=[...]` list — do not replace the existing tool unless asked.
- If a live Bedrock/AgentCore call is unavailable or slow while iterating, fall back to
  testing the clustering tool and prompt logic against a cached/sample clustered JSON
  rather than blocking all progress on live infra.

## Known-good example (use to sanity-check any prompt changes)
Input clusters (from the seeded demo incident):
- "DB connection pool exhausted" — count 3, first seen T+0s
- "API timeout: /checkout" — count 2, first seen T+3s
- "502 Bad Gateway from load balancer" — count 4, first seen T+6s

Expected reasoning: root cause = DB pool exhaustion; cascade = API timeouts then 502s;
fix = increase pool size / add query timeouts / investigate recent deploy.
If a prompt change causes this example to produce a different root cause, treat that as
a regression and revert or fix before moving on.
