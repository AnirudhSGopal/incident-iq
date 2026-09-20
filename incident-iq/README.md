# IncidentIQ

**An AI agent that reads messy production logs during an outage and instantly explains what broke, why, and how to fix it.**

Built for: AWS hackathon (Bedrock + Strands Agents + AgentCore + Claude Code/Kiro)

---

## 1. Problem

On-call engineers waste 15–30+ minutes manually scrolling through thousands of scattered
log lines across services to find the root cause of an incident. Most of what they see is
downstream noise, not the actual cause.

## 2. Who it's for

On-call software engineers, DevOps, and SRE teams.

## 3. What it does

1. Reads a window of production logs (from CloudWatch)
2. Clusters similar errors together (reduces noise)
3. An AI agent reasons over the clustered, timestamped errors to determine:
   - What broke first (root cause)
   - What broke *because* of that (the cascade)
   - What to do about it (suggested fix)
4. Returns a clean, structured, plain-English answer

## 4. Architecture

```
┌─────────────────────────┐
│ Synthetic log generator │  (simulates a real incident for reliable demos)
│  generate_incident.py   │
└────────────┬─────────────┘
             │ writes to
             ▼
┌─────────────────────────┐
│   Amazon CloudWatch Logs │
└────────────┬─────────────┘
             │ queried by
             ▼
┌─────────────────────────────────┐
│  Strands Tool: get_clustered_logs│   src/tools/log_cluster.py
│  (groups errors, reduces noise)  │
└────────────┬─────────────────────┘
             │ clustered JSON
             ▼
┌─────────────────────────────────┐
│   Strands Agent (IncidentIQ)     │   src/agent.py
│   Model: Claude via Bedrock      │
│   Reasons: root cause → cascade  │
│           → fix → summary        │
└────────────┬─────────────────────┘
             │ deployed to
             ▼
┌─────────────────────────────────┐
│  Amazon Bedrock AgentCore Runtime│
└────────────┬─────────────────────┘
             │ invoked by
             ▼
┌─────────────────────────────────┐
│  Trigger: CLI script or frontend │   src/trigger.py / frontend/index.html
│  button ("Analyze Incident")     │
└──────────────────────────────────┘
```

## 5. Tech stack

| Layer | Technology |
|---|---|
| Agent framework | Strands Agents SDK (Python) |
| LLM | Amazon Bedrock (Claude) |
| Agent hosting | Amazon Bedrock AgentCore Runtime |
| Log storage | Amazon CloudWatch Logs |
| Log querying | CloudWatch Logs Insights / filter_log_events (boto3) |
| Dev tooling | Claude Code / Kiro (scaffolding), uv (package mgmt) |
| Interface | Static HTML/JS page or CLI trigger |
| Optional storage | DynamoDB (past incident history) |
| Optional notify | SNS / Slack webhook |

## 6. Project structure

```
incident-iq/
├── README.md                      ← this file
├── IMPLEMENTATION_PLAN.md         ← step-by-step build order + checklist
├── CLAUDE.md                      ← "skill"/steering file for Claude Code & Kiro
├── prompts/
│   └── system_prompt.md           ← the agent's system prompt (source of truth)
├── src/
│   ├── generate_incident.py       ← pushes fake log data to CloudWatch
│   ├── tools/
│   │   └── log_cluster.py         ← Strands tool: fetch + cluster logs
│   ├── agent.py                   ← Strands agent definition
│   └── trigger.py                 ← CLI script to run the agent end-to-end
└── frontend/
    └── index.html                 ← single-button demo UI
```

## 7. Setup

```bash
cd incident-iq
python -m venv .venv
source .venv/bin/activate
pip install strands-agents strands-agents-tools boto3

aws sts get-caller-identity     # confirm credentials
aws configure get region        # confirm region (e.g. us-west-2)
```

Confirm Bedrock model access is enabled in the Console (Bedrock → Model access → Claude).

## 8. Run order (local, before deploying)

```bash
python src/generate_incident.py     # 1. seed fake incident logs
python src/trigger.py               # 2. run the agent locally end-to-end
```

Only deploy to AgentCore once step 2 above produces a correct, sensible answer.

## 9. One-line pitch

> "IncidentIQ turns a 20-minute manual log investigation into a 5-second AI-generated answer."
