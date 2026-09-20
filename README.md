# IncidentIQ

**An AI-powered Site Reliability Engineering (SRE) diagnostic tool that cuts through production log noise during an outage and delivers the root cause, failure cascade, and remediation steps in seconds.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Amazon%20Bedrock%20(Claude)-orange.svg)](https://aws.amazon.com/bedrock/)
[![Framework](https://img.shields.io/badge/Agent%20Framework-Strands%20SDK-purple.svg)](https://github.com/strands-agents)
[![AWS SAM](https://img.shields.io/badge/IaC-AWS%20SAM-red.svg)](https://aws.amazon.com/serverless/sam/)
[![Tests](https://img.shields.io/badge/Tests-13%20passed-brightgreen.svg)](tests/)

---

## 1. Problem

During a major production outage, on-call engineers often drown in thousands of log events across distributed microservices. Finding the true root cause takes 15–30 minutes of manual triage because the vast majority of log lines (timeouts, 502/503 errors, retry exhaustion) are merely **downstream symptoms**, not the initiating failure.

## 2. Solution: IncidentIQ

IncidentIQ automates initial outage diagnosis:
1. **Pulls recent logs** from a target CloudWatch log group within a configurable time window (1–60 minutes).
2. **Normalizes & clusters logs** using regex-based pattern reduction (`\d+ -> #`, route parameters `/[a-z]+ -> /*`) to collapse thousands of noisy events into chronologically ordered error signatures.
3. **Reasons with Claude via Amazon Bedrock** (using the Strands Agents SDK) to distinguish initiating resource/system failures from downstream symptoms.
4. **Returns a strict JSON response** with:
   - **Root Cause:** The initiating failure point.
   - **Cascade:** The chronological chain of failure consequences.
   - **Suggested Fix:** Concrete, immediate remediation steps.
   - **Summary:** Plain-English briefing suitable for postmortems and executive updates.

---

## 3. Architecture

```
┌────────────────────────────────────────────────────────┐
│                   Synthetic Incident Seeder            │
│                 src/generate_incident.py               │
│        (db_pool | memory_leak | payment_gateway)       │
└───────────────────────────┬────────────────────────────┘
                            │ writes log events
                            ▼
┌────────────────────────────────────────────────────────┐
│                  Amazon CloudWatch Logs                │
│                 e.g. /incident-iq/demo                 │
└───────────────────────────┬────────────────────────────┘
                            │ FilterLogEvents
                            ▼
┌────────────────────────────────────────────────────────┐
│             Strands Tool: get_clustered_logs           │
│                src/tools/log_cluster.py                │
│     (normalizes patterns, counts, computes timestamps) │
└───────────────────────────┬────────────────────────────┘
                            │ clean clustered signatures
                            ▼
┌────────────────────────────────────────────────────────┐
│               Strands Agent (IncidentIQ)               │
│                      src/agent.py                      │
│            Bedrock Claude + SRE System Prompt          │
│            Causal reasoning → JSON extraction          │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
      Local Invocation           Serverless Deployment
               │                          │
               ▼                          ▼
┌───────────────────────────┐ ┌───────────────────────────┐
│     CLI (trigger.py)      │ │   AWS API Gateway (prod)  │
│   Local Web (server.py)   │ │      (x-api-key auth)     │
└───────────────────────────┘ └─────────────┬─────────────┘
                                            │
                                            ▼
                              ┌───────────────────────────┐
                              │ AWS Lambda Handler        │
                              │ (src/lambda_handler.py)   │
                              └─────────────┬─────────────┘
                                            │ stores result
                                            ▼
                              ┌───────────────────────────┐
                              │ Amazon DynamoDB           │
                              │ (IncidentIQHistory)       │
                              └───────────────────────────┘
```

---

## 4. Repository Structure

```text
incident-iq/
├── README.md                      ← Project overview and setup guide (Root)
└── incident-iq/
    ├── README.md                  ← Component-level documentation
    ├── samconfig.toml             ← SAM deployment configuration
    ├── requirements.txt           ← Local development & testing dependencies
    ├── infra/
    │   └── template.yaml          ← SAM Template: API Gateway, Lambda, DynamoDB, Alarms
    ├── prompts/
    │   └── system_prompt.md       ← SRE reasoning prompt & JSON output contract
    ├── frontend/
    │   └── index.html             ← Zero-dependency, dark-themed incident dashboard
    ├── src/
    │   ├── agent.py               ← Strands Agent definition with Bedrock model
    │   ├── config.py              ← Environment variable loader
    │   ├── generate_incident.py   ← Incident simulator (db_pool, memory_leak, payment_gateway)
    │   ├── lambda_handler.py      ← AWS Lambda entrypoint with DynamoDB persistence & CORS
    │   ├── server.py              ← Local Flask demo server (:5000)
    │   ├── trigger.py             ← CLI runner with colored terminal output
    │   └── tools/
    │       └── log_cluster.py     ← CloudWatch log fetcher & pattern normalization tool
    └── tests/
        ├── test_agent.py          ← Agent execution & prompt contract tests
        ├── test_lambda_handler.py ← API Gateway handler, validation & DynamoDB tests
        └── test_log_cluster.py    ← Log clustering algorithm & bounds tests
```

---

## 5. Getting Started

### Prerequisites
* Python 3.11+
* Active AWS Account with **Amazon Bedrock** model access enabled for Anthropic Claude
* AWS CLI configured (`aws configure`) or environment credentials set
* AWS SAM CLI (for serverless deployment)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AnirudhSGopal/incident-iq.git
   cd incident-iq/incident-iq
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in `incident-iq/`:
   ```env
   AWS_DEFAULT_REGION=us-west-2
   LOG_GROUP=/incident-iq/demo
   LOG_STREAM=incident-001
   ```

---

## 6. Usage & Execution Modes

### Mode A: Seed Synthetic Incidents
Populate CloudWatch with realistic failure scenarios:
```bash
# Scenario 1: Database connection pool exhaustion (Default)
python src/generate_incident.py --scenario db_pool

# Scenario 2: Memory leak leading to container OOM kills
python src/generate_incident.py --scenario memory_leak

# Scenario 3: External payment gateway outage & circuit breaker trip
python src/generate_incident.py --scenario payment_gateway
```

### Mode B: CLI Runner (`src/trigger.py`)
Run end-to-end incident analysis straight from the terminal with color-coded bulleted output:
```bash
python src/trigger.py --log-group /incident-iq/demo --minutes-back 15
```

### Mode C: Local Web Server (`src/server.py`)
Launch a local demo web server hosting the dashboard UI and local analysis API:
```bash
python src/server.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

### Mode D: Static Frontend (`frontend/index.html`)
Open `frontend/index.html` directly in any web browser. 
* Non-sensitive inputs (API Endpoint URL, Log Group, Minutes back) persist across page refreshes.
* **Security guarantee:** The `x-api-key` is never stored in `localStorage`; it remains memory-only for the session.

---

## 7. Running the Automated Tests

The test suite runs completely offline with 100% mocked AWS services using `unittest.mock`:

```bash
pytest tests/ -v
```

All 13 tests validate:
* Required parameter validation (e.g. rejection of missing `log_group`)
* Time bounding checks ($1 \le \text{minutes\_back} \le 60$)
* Log clustering and pattern normalization
* Lambda HTTP status codes (200, 400, 500) and DynamoDB persistence
* JSON parsing and regex unwrapping of agent responses

---

## 8. Deploying to AWS (Serverless SAM)

To deploy the production-ready serverless stack:

```bash
# 1. Build the Lambda package
sam build --template infra/template.yaml

# 2. Deploy the stack (guided first time)
sam deploy --guided
```

### Retrieve your API Key
After deployment, retrieve the generated API key:
```bash
aws apigateway get-api-keys \
  --include-values \
  --query "items[?name=='incident-iq-api-prod'].value | [0]" \
  --output text \
  --region us-west-2
```

Paste your **API Endpoint URL** and **API Key** into `frontend/index.html` to run analyses against your live AWS environment.

### Teardown
To remove all provisioned resources:
```bash
sam delete --stack-name incident-iq --region us-west-2
```

---

## 9. License

This project is licensed under the MIT License.

