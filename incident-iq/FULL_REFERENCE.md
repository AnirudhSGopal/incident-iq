# IncidentIQ — Full Reference

Everything in one place: architecture, tech stack, constraints, files, and prompts.
(Individual files are still the source of truth — this document summarizes them.)

---

## 1. Architecture

```
Synthetic log generator ──writes──▶ CloudWatch Logs
                                          │
                                   (query + cluster)
                                          ▼
                          Strands tool: get_clustered_logs
                                          │
                                   clustered JSON
                                          ▼
                          Strands Agent (IncidentIQ)
                          model: Bedrock Claude
                          reads: prompts/system_prompt.md
                                          │
                                deployed to (stretch goal)
                                          ▼
                          Amazon Bedrock AgentCore Runtime
                                          │
                                  invoked by
                                          ▼
                     src/trigger.py (CLI)  or  frontend/index.html
```

## 2. Full tech stack

| Layer | Technology | Required or optional |
|---|---|---|
| Agent framework | Strands Agents SDK (Python) | Required |
| LLM | Amazon Bedrock (Claude) | Required |
| Log storage | Amazon CloudWatch Logs | Required |
| Log querying | boto3 `filter_log_events` | Required |
| Agent hosting | Amazon Bedrock AgentCore Runtime | Stretch goal |
| Interface | CLI (`trigger.py`) or static HTML page | Required (pick one) |
| Dev tooling | Claude Code and/or Kiro | Available in sandbox |
| Package mgmt | pip or uv | Required |
| History storage | DynamoDB | Optional, only if time remains |
| Notifications | SNS or Slack webhook | Optional, only if time remains |

## 3. Constraints (do not violate these while building)

- **Time:** 8-hour sandbox window. Budget accordingly — see IMPLEMENTATION_PLAN.md.
- **No real production data.** Use only the seeded synthetic incident.
- **No auth, no multi-tenancy, no persistence** unless explicitly added as a stretch goal.
- **Never hand raw, unclustered logs to the agent** — always go through the clustering
  tool first, both for cost (token usage) and for reasoning quality.
- **Output shape is fixed.** Any change to the JSON contract must update
  `prompts/system_prompt.md`, the parsing in `src/trigger.py`, and `frontend/index.html`
  together — never one without the others.
- **Bedrock model access must be enabled** in the AWS account before any of this works —
  verify this first, not after building.
- **Region must be consistent** across `generate_incident.py`, `log_cluster.py`, and
  whatever region Bedrock/AgentCore access is enabled in.
- **AgentCore deployment is optional for demo success.** A working local agent
  (Phase 3 in the implementation plan) is an acceptable fallback demo on its own.

## 4. Files in this project and what each one is for

| File | Purpose |
|---|---|
| `README.md` | Overview, setup, run order |
| `IMPLEMENTATION_PLAN.md` | Phase-by-phase build checklist, priority order, demo script |
| `CLAUDE.md` / `.kiro/steering/project.md` | Project-wide context read by Claude Code/Kiro every session |
| `.claude/skills/incident-analysis/SKILL.md` / `.kiro/skills/incident-analysis/SKILL.md` | Scoped skill: how to run/extend/deploy the incident analysis workflow specifically |
| `prompts/system_prompt.md` | The agent's exact reasoning instructions and output contract |
| `src/generate_incident.py` | Seeds synthetic cascading-failure logs into CloudWatch |
| `src/tools/log_cluster.py` | Strands tool: fetches + clusters logs |
| `src/agent.py` | Strands agent definition, wires tool + system prompt |
| `src/trigger.py` | CLI entrypoint — the "one button press" for the demo |
| `frontend/index.html` | Optional single-button web UI alternative to the CLI |

## 5. The complete prompt set

### 5.1 Agent system prompt (full text lives in `prompts/system_prompt.md`)
Purpose: defines how the agent reasons over clustered logs and the exact JSON shape
it must return. This is the single most important file to get right — if the agent's
answers are wrong or vague, edit this file first.

### 5.2 Prompt sent to the agent at runtime (in `src/agent.py`)
```
Analyze the current incident. Use your tool to fetch clustered logs from log group
'{log_group}' for the last {minutes_back} minutes, then respond with the required
JSON output.
```
This is intentionally short — the heavy reasoning instructions live in the system
prompt, not here. Keep this runtime prompt minimal; it just tells the agent to act.

### 5.3 Prompt/instruction if using Claude Code or Kiro to scaffold further
Use this pattern when asking Claude Code/Kiro to extend the project:
```
Follow .claude/skills/incident-analysis/SKILL.md and CLAUDE.md for context and
constraints. [Describe the specific change, e.g., "Add a second synthetic incident
scenario simulating a memory leak instead of DB pool exhaustion, following the same
pattern as generate_incident.py."]
```
Referencing the skill/steering files explicitly in your instruction ensures Claude
Code/Kiro follows the build order and output contract instead of improvising a
different structure.

## 6. Minimum viable demo (if time runs short)
Phases 0–3 only (env setup → seed data → clustering tool → local agent reasoning).
Skip AgentCore deployment, skip the frontend, use `src/trigger.py` output directly
in your live demo. This is a legitimate, complete demo on its own.

## 7. One-line pitch
> "IncidentIQ turns a 20-minute manual log investigation into a 5-second AI-generated
> root-cause answer, built with Strands Agents on Amazon Bedrock."
