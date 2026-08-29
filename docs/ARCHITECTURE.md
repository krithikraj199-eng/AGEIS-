# AEGIS Ω — Architecture and operating analysis

## What is implemented

The repository now contains three connected layers:

1. **Digital world** — the institution builder creates 130 typed assets. NetworkX stores 235 directed dependencies. Metrics drift with time-of-day load, thresholds emit events, and ten chaos scenarios inject controlled failure chains.
2. **Autonomous intelligence** — a 14-agent registry drives Sentinel, Investigator, Evidence, Dependency, Security, Root Cause, Planner, Counterfactual, Risk, Executor, Verifier, Recovery, Memory, and Prediction stages. Every stage creates an incident timeline item, trace, and audit entry.
3. **Governance and learning** — capability authorization guards tools, risk scores determine whether execution is automatic or escalated, SQLite stores episodic/procedural memory, and a trend engine predicts threshold crossings.

The Agent Gateway validates sender/recipient identities, rate-limits traffic, bounds payload size, neutralizes common prompt-injection phrases in untrusted telemetry, and audits every routed stage. Active predictions can be converted into predictive incidents; those incidents use the same plan, risk, execution, verification, and learning path before a threshold breach becomes an outage.

## End-to-end monitoring flow

```text
Metric drift / chaos event
        ↓
Sentinel correlation → one incident
        ↓
Investigation → raw events + hypotheses
        ↓
Evidence validation + dependency blast radius + security classification
        ↓
Root-cause confidence + historical memory match
        ↓
Three plans → counterfactual outcomes → risk policy
        ↓
Scoped simulated tool execution
        ↓
Verification ── failed → rollback → next approved plan
        │
        └── success → resolve → write institutional memory
```

### How monitoring works

- `backend/digital_world/metrics.py` updates CPU, memory, disk, latency, error rate, connection count, response time, throughput, and queue depth. Threshold checks remain deterministic.
- `backend/digital_world/events.py` publishes metric, ambient, and chaos events. Sentinel observes the event bus. A startup grace period prevents noisy baseline data from creating false incidents.
- `backend/digital_world/dependencies.py` calculates direct and transitive dependents, blast radius, cascade paths, critical assets, and single points of failure.
- `backend/agents/pipeline.py` owns the incident lifecycle. Chaos events are correlated through a failure ID and correlation ID; critical natural events are deduplicated with a per-asset cooldown.

### How diagnosis works

- Investigator gathers recent events for every affected asset and creates competing hypotheses.
- Evidence Agent only accepts actual threshold breaches from the metric snapshot.
- Dependency Agent measures downstream impact from the suspected target.
- Security Agent separates security attacks, deployment configuration errors, and operational failures.
- Root Cause combines the target, scenario/pattern, evidence count, blast radius, and prior memory into a confidence-scored diagnosis.
- When optional Gemini mode is enabled, Gemini adds advisory prose. It does not choose tools or override policy.

### How fixing works

- Planner creates three scenario-aware plans with expected recovery, downtime, and rollback method.
- Counterfactual Engine estimates recovery and secondary-failure probability for each future.
- Risk Engine uses the allow-list in `backend/tools/remediation.py`: 0–30 auto-executes, 31–60 requires supervisor review, 61–80 requires a human, and over 80 is blocked.
- Executor can mutate only in-memory digital-twin assets and chaos records. It cannot issue shell commands or touch real enterprise infrastructure.
- Verifier requires no critical affected assets, no active related failure, and at least 70% healthy affected assets.
- A failed attempt transitions to rollback, selects the next approved plan, and verifies again. The demo intentionally exercises this branch.

### How learning and prevention work

- `backend/memory/bank.py` writes incident outcome, root cause, pattern, action, affected assets, and recovery duration to SQLite.
- Procedural memory aggregates uses, successes, success rate, and mean recovery time per pattern/action. Future planning boosts a historically successful action.
- `backend/agents/predictor/engine.py` performs linear-regression trend scans over metric history. It creates a prediction when a warning threshold is likely within the configured step horizon.

## Main API groups

- `/api/world/*`, `/api/assets/*`, `/api/events/*`, `/api/graph/*` — observable institution state.
- `/api/chaos/*` — controlled failure injection and recovery.
- `/api/incidents/*` — incident records and retries.
- `/api/agents`, `/api/traces`, `/api/audit` — governance and observability.
- `/api/memory`, `/api/predictions` — learning and prediction.
- `/api/demo/run` — complete autonomous demonstration, optionally waiting for final verification.
- `/ws` — real-time world-state stream.

## Important scope

This is a safe digital-twin demonstration. “Fix” actions modify simulated assets only. Connecting the same executor to production systems would require environment-specific credentials, approvals, change windows, secrets management, and real rollback adapters. Cloud Run, Pub/Sub, Cloud SQL/Firestore, and Google ADK deployment remain deployment integrations rather than requirements for the local demo.
