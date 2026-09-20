# IncidentIQ

**An AI agent that reads production logs during an outage and instantly explains what broke, why, and how to fix it.**

---

## 1. Problem

On-call engineers waste 15–30 minutes manually scrolling through thousands of scattered log lines across services to find the root cause of an incident. Most of what they see is downstream noise — not the actual cause.

## 2. Who it's for

On-call software engineers, DevOps, and SRE teams who operate workloads on AWS.

## 3. What it does

1. Reads a window of production logs from a CloudWatch log group you specify
2. Clusters similar errors together (reduces noise)
3. An AI agent reasons over the clustered, timestamped errors to determine:
   - What broke first (root cause)
   - What broke *because* of that (the cascade)
   - What to do about it (suggested fix)
4. Returns a clean, structured, plain-English answer via a REST API

## 4. Architecture

```
┌─────────────────────────┐
│ Synthetic log generator │  (simulates a real incident for demos)
│  generate_incident.py   │
└────────────┬─────────────┘
             │ writes to
             ▼
┌─────────────────────────┐
│  Amazon CloudWatch Logs  │
└────────────┬─────────────┘
             │ queried by
             ▼
┌──────────────────────────────────┐
│  Strands Tool: get_clustered_logs│   src/tools/log_cluster.py
│  (groups errors, reduces noise)  │
└────────────┬─────────────────────┘
             │ clustered JSON
             ▼
┌──────────────────────────────────┐
│   Strands Agent (IncidentIQ)     │   src/agent.py
│   Model: Claude via Bedrock      │
│   Reasons: root cause → cascade  │
│           → fix → summary        │
└────────────┬─────────────────────┘
             │ wrapped by
             ▼
┌──────────────────────────────────┐
│  AWS Lambda + API Gateway        │   infra/template.yaml
│  POST /analyze  (API-key auth)   │
└────────────┬─────────────────────┘
             │ called by
             ▼
┌──────────────────────────────────┐
│  frontend/index.html             │
│  (enter endpoint, key, log group)│
└──────────────────────────────────┘
```

## 5. Tech stack

| Layer | Technology |
|---|---|
| Agent framework | Strands Agents SDK (Python) |
| LLM | Amazon Bedrock (Claude 3) |
| Compute | AWS Lambda (Python 3.11) |
| API | Amazon API Gateway REST API (API-key auth) |
| Log storage | Amazon CloudWatch Logs |
| Incident history | Amazon DynamoDB |
| IaC | AWS SAM (`infra/template.yaml`) |
| Interface | Static HTML/JS (`frontend/index.html`) or CLI (`src/trigger.py`) |

## 6. Project structure

```
incident-iq/
├── README.md
├── samconfig.toml                 ← SAM deploy defaults (created on first deploy)
├── infra/
│   └── template.yaml             ← SAM template: Lambda, API GW, DynamoDB
├── src/
│   ├── requirements.txt          ← strands-agents, boto3
│   ├── lambda_handler.py         ← Lambda entry point
│   ├── agent.py                  ← Strands agent definition
│   ├── config.py                 ← environment / model config
│   ├── generate_incident.py      ← pushes synthetic log data to CloudWatch
│   ├── trigger.py                ← CLI script to run the agent locally
│   └── tools/
│       └── log_cluster.py        ← Strands tool: fetch + cluster CW logs
└── frontend/
    └── index.html                ← browser UI (endpoint + API key + log group)
```

## 7. Prerequisites

- AWS account with Bedrock **Claude** model access enabled
  (Bedrock Console → Model access → enable Anthropic Claude)
- AWS credentials configured locally (`aws configure` or SSO)
- Python 3.11+
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)

## 8. Local setup (run before deploying)

```bash
cd incident-iq
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install strands-agents boto3

aws sts get-caller-identity      # confirm credentials
aws configure get region         # confirm region (e.g. us-west-2)
```

Seed a synthetic incident into CloudWatch, then run the agent locally to
verify a sensible answer before deploying:

```bash
python src/generate_incident.py   # 1. write fake incident logs to CloudWatch
python src/trigger.py             # 2. run the agent end-to-end locally
```

## 9. Deploy to AWS

```bash
# Build (Linux-targeted wheels, no Docker required)
PIP_PLATFORM=manylinux2014_x86_64 \
PIP_ONLY_BINARY=:all: \
sam build --template infra/template.yaml

# First deploy — answer the guided prompts:
#   Stack name:   incident-iq
#   Region:       us-west-2   (or your preferred region)
#   Confirm changes before deploy: y
#   Allow SAM to create IAM roles: y
#   Save to samconfig.toml: y
sam deploy --guided

# Subsequent deploys — uses saved samconfig.toml:
sam deploy
```

> **Windows note:** run the `PIP_PLATFORM` / `PIP_ONLY_BINARY` lines as
> PowerShell `$env:` assignments before `sam build`, or Docker Desktop must
> be running and you must add `--use-container`.

## 10. Getting your API key after deployment

SAM automatically creates an API key and usage plan. Retrieve the key value
with the command printed in the deploy Outputs, or run:

```bash
aws apigateway get-api-keys \
  --include-values \
  --query "items[?name=='incident-iq-api-prod'].value | [0]" \
  --output text \
  --region us-west-2
```

Keep this value — you will paste it into the browser UI.

## 11. Using the browser UI

1. Open `frontend/index.html` in any browser (no web server needed — it
   runs as a local file).
2. Fill in the three fields:

   | Field | Where to find it |
   |---|---|
   | **API Endpoint URL** | Printed in the SAM deploy Outputs as `ApiEndpoint` |
   | **API Key** | Retrieved with the command in Section 10 above |
   | **CloudWatch Log Group** | The log group your application writes to (e.g. `/my-app/prod`) |

3. Optionally adjust **Minutes back** (default 10) to widen or narrow the
   log window.
4. Click **Analyze** — the response shows root cause, cascade, suggested
   fix, and a plain-English summary.

Values are saved in `localStorage` and persist across page refreshes.

## 12. Pointing at your own log group

Pass any CloudWatch log group that your application already writes to.
The Lambda's IAM policy is scoped to the log group name you set during
`sam deploy` (the `LogGroupName` parameter, default `/incident-iq/demo`).

To allow analysis of a different log group **without redeploying**, you can
redeploy with the parameter overridden:

```bash
sam deploy --parameter-overrides LogGroupName=/your-app/production
```

Or update the `LogGroupName` default in `infra/template.yaml` and redeploy.

## 13. Cleaning up

```bash
sam delete --stack-name incident-iq --region us-west-2
```

This removes the Lambda, API Gateway, DynamoDB table, and all associated
IAM roles created by the stack.

## 14. One-line pitch

> "IncidentIQ turns a 20-minute manual log investigation into a 5-second AI-generated answer."
