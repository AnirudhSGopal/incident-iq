# Implementation Plan — IncidentIQ

Build in this exact order. Do not skip ahead — each step is tested alone before
connecting it to the next. This order protects your time in an 8-hour sandbox.

---

## Phase 0 — Environment (target: 30 min)
- [ ] `aws sts get-caller-identity` succeeds
- [ ] Bedrock model access enabled for Claude in your region
- [ ] `pip install strands-agents strands-agents-tools boto3` succeeds
- [ ] Confirm whether Kiro or Claude Code CLI is available in the sandbox

## Phase 1 — Synthetic data (target: 30–45 min)
- [ ] Run `src/generate_incident.py`
- [ ] Verify in CloudWatch console: log group `/incident-iq/demo` has the seeded
      cascading-failure log lines (DB pool exhaustion → API timeout → 502s)
- [ ] **Test in isolation. Do not proceed until you can see the logs in the console.**

## Phase 2 — Clustering tool (target: 60–90 min)
- [ ] Implement `src/tools/log_cluster.py`
- [ ] Test it standalone (call the function directly in a Python shell, not via the agent)
- [ ] Confirm output groups the ~10 log lines into 3 clean clusters with counts + first-seen timestamps
- [ ] **Test in isolation. Do not proceed until clustering output looks correct.**

## Phase 3 — Agent reasoning (target: 90 min)
- [ ] Implement `src/agent.py` using the system prompt in `prompts/system_prompt.md`
- [ ] Run `src/trigger.py` locally (no AgentCore yet — just run the Python agent directly)
- [ ] Confirm the agent's output correctly identifies:
      root_cause = DB connection pool exhaustion
      cascade = [API timeouts, then 502s]
      suggested_fix = something sensible
- [ ] Iterate on the system prompt if the reasoning is vague or wrong
- [ ] **This is your safety-net milestone. If nothing else works, this alone is demoable.**

## Phase 4 — Deployment to AgentCore (target: 60–90 min, treat as stretch goal)
- [ ] Package the agent for AgentCore Runtime
- [ ] Deploy
- [ ] Invoke the deployed endpoint with the same test data, confirm same quality of output
- [ ] If this is fighting you and eating time: **fall back to running locally for the demo.**
      A working local agent beats a half-broken deployed one.

## Phase 5 — Interface (target: 45–60 min)
- [ ] Wire up `frontend/index.html` (or just use `src/trigger.py` as the "demo trigger" if
      time is short — a CLI demo is completely acceptable)
- [ ] One click/command → full pipeline runs → clean result displayed

## Phase 6 — Polish & safety net (target: remaining time)
- [ ] Record a 60–90 second screen capture of the full flow working, as backup
- [ ] Pre-warm the Bedrock/AgentCore call once before your demo slot (avoid cold-start lag)
- [ ] (Optional, only if time remains) DynamoDB history table
- [ ] (Optional, only if time remains) Slack webhook / SNS notification
- [ ] Practice your 60–90 second pitch (see below)

---

## Priority order if you run low on time

1. Clustering tool working ✅ — non-negotiable, everything depends on it
2. Agent reasoning correct, run locally ✅ — **this is your minimum viable demo**
3. Deployed to AgentCore — bonus, shows deeper AWS integration
4. Frontend polish, history, notifications — only if time remains

---

## Demo script (say this while clicking through)

> "This is what an on-call engineer sees at 2am — [show messy CloudWatch logs] — hundreds
> of lines, no clear answer. Now watch what happens when I click Analyze [click] — our
> agent, built with Strands and running on Amazon Bedrock, reasons through this in seconds
> [result appears] — root cause: DB pool exhaustion, here's the cascade, here's the fix.
> This turns a 20-minute manual investigation into a 5-second answer."
