# Project: IncidentIQ

You are helping build IncidentIQ, an AI agent that diagnoses root cause during a
production incident by reasoning over clustered log data.

## Context (read this before writing any code)

- **Region:** us-west-2 (confirm against `aws configure get region` — adjust if different)
- **Package manager:** pip (or uv if available in this sandbox)
- **Python version:** 3.10+
- **Agent framework:** Strands Agents SDK (`strands-agents`, `strands-agents-tools`)
- **Model:** default Bedrock model provider (Claude), via Strands' built-in Bedrock integration
- **Deploy target:** Amazon Bedrock AgentCore Runtime
- **Pattern:** single agent with one custom tool (not multi-agent) — keep this simple,
  this is a time-boxed hackathon build, not a production system

## Project structure (do not deviate from this layout)

```
incident-iq/
├── src/
│   ├── generate_incident.py   # synthetic CloudWatch log seeder
│   ├── tools/
│   │   └── log_cluster.py     # Strands @tool: fetch + cluster CloudWatch logs
│   ├── agent.py                # Strands Agent definition, uses prompts/system_prompt.md
│   └── trigger.py              # CLI entrypoint: runs the full pipeline once
├── prompts/
│   └── system_prompt.md        # source of truth for the agent's system prompt
└── frontend/
    └── index.html              # single-button demo UI, calls the agent
```

## Build order (follow this strictly — do not jump ahead)

1. `generate_incident.py` must work and be verified in the CloudWatch console FIRST.
2. `log_cluster.py` must be tested standalone (call the function directly) BEFORE wiring
   it into the agent.
3. `agent.py` must be run and validated locally (no deployment) BEFORE attempting
   AgentCore deployment.
4. AgentCore deployment is a stretch goal — if it's not working with time remaining,
   fall back to the local agent for the demo. Say so plainly rather than hiding it.
5. The frontend/trigger is the last thing built — it is a thin wrapper around a pipeline
   that already works. Never debug agent logic and interface code at the same time.

## Output contract (do not change this shape without updating system_prompt.md too)

The agent must always return JSON of this shape:

```json
{
  "root_cause": "string",
  "cascade": ["string", "string", "..."],
  "suggested_fix": "string",
  "summary": "2-3 sentence plain-English summary"
}
```

## Constraints

- No user auth, no multi-tenancy, no real production log integration — out of scope.
- Keep the demo to ONE seeded incident scenario. Do not build multiple scenarios unless
  all phases above are complete with time remaining.
- Every new function should be testable in isolation (print output, don't assume it works).
- If Bedrock/AgentCore calls are slow or fail during testing, that's expected — always
  keep a cached/known-good sample response available as a fallback for the live demo.

## When asked to scaffold or extend code

- Reuse the `@tool` decorator pattern from `strands` for any new tool.
- Reuse the JSON output contract above — don't invent new fields.
- Prefer boto3 for any AWS calls outside of what Strands handles natively.
- Keep functions short and single-purpose; this is a hackathon build, favor working code
  over abstraction.
