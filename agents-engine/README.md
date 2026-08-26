# AEGIS Ω — Intelligence Engine

> **Autonomous Multi-Agent Resilience, Root-Cause Synthesis & Governance Infrastructure**
> 
> *Member 2 Module*: AI Intelligence Engine and Governance Layer.

---

## 1. Project Purpose

**AEGIS Ω** is an autonomous multi-agent intelligence platform engineered to detect, diagnose, plan, govern, and remediate incidents across complex distributed architectures. 

Within the AEGIS Ω ecosystem:
- **Member 1 (Digital World)** simulates the physical and cloud infrastructure, managing asset topologies, live telemetry metrics, dependency graphs, event streams, and chaos injection.
- **Member 2 (Intelligence Engine & Governance — this repository)** houses the reasoning, multi-agent coordination, root cause analysis, risk evaluation, counterfactual simulation, safety policy gates, and automated recovery orchestration.

The Intelligence Engine continuously ingests infrastructure telemetry, correlates anomalies, isolates root causes across multi-tier dependency chains, formulates verifiable remediation plans, passes them through strict governance policy gates, and dispatches automated actions back to the digital environment.

---

## 2. Architecture

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 MEMBER 1: DIGITAL WORLD                │
                  │   (Assets, Dependency Graph, Chaos Injection, Streams) │
                  └──────────────────────────┬─────────────────────────────┘
                                             │  Event Streams / WebSockets / REST
                                             ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             AEGIS Ω — INTELLIGENCE ENGINE (MEMBER 2)                             │
│                                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                IN-MEMORY PUB/SUB EVENT BUS                               │   │
│   └─────────────────┬───────────────────────┬───────────────────────────────┬────────────────┘   │
│                     │                       │                               │                    │
│                     ▼                       ▼                               ▼                    │
│   ┌───────────────────────────┐ ┌───────────────────────────┐ ┌──────────────────────────────┐   │
│   │   PERCEPTION & TRIAGE     │ │    DIAGNOSTICS & REASONING│ │     PLANNING & GOVERNANCE    │   │
│   │ ------------------------- │ │ ------------------------- │ │ ---------------------------- │   │
│   │ • Sentinel Agent          │ │ • Root Cause Agent        │ │ • Planner Agent              │   │
│   │ • Investigator Agent      │ │ • Dependency Agent        │ │ • Counterfactual Agent       │   │
│   │ • Evidence Agent          │ │ • Security Agent          │ │ • Risk Agent                 │   │
│   └─────────────┬─────────────┘ └─────────────┬─────────────┘ └──────────────┬───────────────┘   │
│                 │                             │                              │                   │
│                 └───────────────────────┬─────┴──────────────────────────────┘                   │
│                                         ▼                                                        │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                  GOVERNANCE & SAFETY GATE                                │   │
│   │   • Policy Engine (Allow / Deny / HITL Approval)  • Blast Radius & Safety Constraints    │   │
│   └─────────────────────────────────────┬────────────────────────────────────────────────────┘   │
│                                         ▼                                                        │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                   EXECUTION & VERIFICATION                               │   │
│   │   • Executor Agent                 • Verifier Agent              • Recovery Agent        │   │
│   └─────────────────────────────────────┬────────────────────────────────────────────────────┘   │
│                                         │                                                        │
│                                         ▼ (Remediation / Actuation Dispatch)                     │
└─────────────────────────────────────────┼────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                  ┌────────────────────────────────────────────────────────┐
                  │          DIGITAL WORLD ACTUATORS & REPAIR APIS         │
                  └────────────────────────────────────────────────────────┘
```

### Core Architecture Components
1. **Perception & Ingestion**: Sentinel and Investigator agents ingest telemetry events from the EventBus, correlate time-series metric spikes, and gather cryptographic evidence.
2. **Causal Reasoning & Diagnostics**: Dependency, Security, and Root Cause agents traverse topological graphs to infer the primary culprit behind cascading failures.
3. **Planning & Counterfactual Evaluation**: The Planner generates remediation sequences; the Counterfactual agent simulates "what-if" side effects; the Risk agent scores operational hazard.
4. **Governance Layer**: Enforces zero-trust safety policies, human-in-the-loop (HITL) approval thresholds, and strict compliance before any executor touches production.
5. **Execution, Verification & Rollback**: The Executor runs approved operations, the Verifier confirms metric stabilization, and the Recovery agent manages automated fallbacks.
6. **Observability**: Distributed tracing and performance telemetry instrumented via OpenTelemetry.

---

## 3. Directory Structure

```
agents-engine/
├── runtime/                       # Runtime engine, event bus, and core infrastructure
│   ├── __init__.py
│   ├── config.py                  # Strongly-typed Pydantic settings & env management
│   ├── event_bus.py               # In-memory asynchronous Pub/Sub event bus
│   └── llm.py                     # Google GenAI / Gemini client secure factory
├── agents/                        # 12 Specialized autonomous resilience agents
│   ├── sentinel/                  # Anomaly detection & alert triage
│   ├── investigator/              # Deep log & diagnostic investigation
│   ├── evidence/                  # Proof gathering, snapshots & audit logs
│   ├── dependency/                # Topological graph & blast radius analysis
│   ├── security/                  # Threat vectors & unauthorized access analysis
│   ├── root_cause/                # Causal inference & failure chain synthesis
│   ├── planner/                   # Remediation strategy synthesis
│   ├── counterfactual/            # 'What-if' simulation & side-effect prevention
│   ├── risk/                      # Operational risk scoring & safety limits
│   ├── executor/                  # Action dispatching & actuator interaction
│   ├── verifier/                  # Post-remediation health validation
│   └── recovery/                  # Rollback & secondary failover orchestration
├── tools/                         # Tooling interfaces & execution primitives
│   └── __init__.py
├── governance/                    # Policy enforcement, audit trails, and safety gates
│   ├── __init__.py
│   └── base.py
├── memory/                        # Incident context & episodic memory stores
│   ├── __init__.py
│   └── base.py
├── observability/                 # OpenTelemetry distributed tracing & metrics
│   ├── __init__.py
│   └── telemetry.py
├── mocks/                         # Telemetry generators & chaos simulation
│   ├── __init__.py
│   └── event_generator.py         # Mock event stream & cascading failure generator
├── tests/                         # Automated unit and integration test suite
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_event_bus.py
│   └── test_event_generator.py
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git ignore rules
├── pyproject.toml                 # Packaging & build configuration
├── requirements.txt               # Project dependencies
└── README.md                      # Project documentation
```

---

## 4. Environment Variables

Configuration is loaded from environment variables and `.env` files via Pydantic Settings (`runtime/config.py`).

> [!IMPORTANT]
> `GEMINI_API_KEY` must **NEVER** be hardcoded into any source code file. Always set it through environment variables or a `.env` file.

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | String (Secret) | *None* | Google Gemini API Key used for GenAI agents. |
| `GEMINI_MODEL` | String | `gemini-2.0-flash` | Default Gemini model name. |
| `ENVIRONMENT` | String | `development` | Deployment environment (`development`, `staging`, `production`). |
| `LOG_LEVEL` | String | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `DEBUG` | Boolean | `true` | Enables verbose debug outputs and local spans. |
| `EVENT_BUS_MAX_QUEUE_SIZE` | Integer | `10000` | Maximum queue size for in-memory event bus. |
| `EVENT_BUS_ENABLE_DEAD_LETTER_QUEUE` | Boolean | `true` | Enables dead-letter recording for handler exceptions. |
| `OTEL_SERVICE_NAME` | String | `aegis-omega-intelligence-engine` | Service name tag for OpenTelemetry traces. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | String | `http://localhost:4317` | OTLP collector gRPC/HTTP endpoint. |
| `OTEL_TRACES_SAMPLER` | String | `always_on` | OpenTelemetry sampling strategy. |
| `DIGITAL_WORLD_API_BASE_URL` | String | `http://localhost:8080/api/v1` | Base REST endpoint for Member 1 Digital World. |
| `DIGITAL_WORLD_WS_STREAM_URL` | String | `ws://localhost:8080/api/v1/events/stream` | WebSocket endpoint for Member 1 live telemetry. |
| `DIGITAL_WORLD_API_KEY` | String (Secret) | *None* | Authentication token for Digital World APIs. |

### Setup Local Environment
```bash
cp .env.example .env
# Edit .env and supply your GEMINI_API_KEY
```

---

## 5. How to Run the Mock Event Generator

The `mocks/event_generator.py` module produces telemetry and incident events conforming to the standard schema:

```json
{
    "timestamp": "2026-08-25T13:45:00.000000Z",
    "asset_id": "DATABASE-01",
    "event_type": "DATABASE_TIMEOUT",
    "severity": "CRITICAL",
    "metrics": {
        "query_latency_ms": 32400.0,
        "connection_pool_usage_pct": 100.0,
        "active_connections": 500,
        "deadlocks": 4
    },
    "source": "db_sentinel_collector",
    "correlation_id": "cascade-a1b2c3d4"
}
```

### Supported Event Types
- `CPU_NORMAL`
- `MEMORY_WARNING`
- `DISK_FULL`
- `NETWORK_LATENCY`
- `DATABASE_TIMEOUT`
- `LOGIN_FAILURE`
- `SERVICE_CRASH`
- `DEPLOYMENT_CHANGE`
- `SECURITY_ALERT`

### 1. Trigger the Cascading Failure Scenario
Simulates the cascading outage sequence:
$$\text{DATABASE-01} \longrightarrow \text{AUTH-01} \longrightarrow \text{API-01} \longrightarrow \text{PORTAL-01}$$

```bash
# Run from the agents-engine directory:
python -m mocks.event_generator --scenario cascade

# With custom inter-event delay (e.g., 1.5 seconds):
python -m mocks.event_generator --scenario cascade --delay 1.5
```

### 2. Stream Randomized Telemetry Events
```bash
python -m mocks.event_generator --scenario random --count 10 --delay 0.5
```

### 3. Generate a Single Event
```bash
python -m mocks.event_generator --scenario single --event-type SECURITY_ALERT --asset-id "AUTH-01"
```

### 4. Programmatic Usage in Python Code / Agents
```python
from mocks.event_generator import EventGenerator, generate_cascading_failure
from runtime.event_bus import get_event_bus

bus = get_event_bus()

# Subscribe agent handler
bus.subscribe("telemetry.*", lambda event: print(f"Agent received: {event.asset_id} -> {event.event_type}"))

# Run generator
generator = EventGenerator(event_bus=bus)
await generator.run_cascading_failure(delay_seconds=0.5)
```

---

## 6. How Future Member 1 APIs Will Replace the Mocks

During initial development, the Intelligence Engine operates on the local in-memory `EventBus` and `mocks/event_generator.py`. When Member 1 completes the simulated Digital World, the transition will occur seamlessly without modifying internal agent reasoning code:

```
[Phase 1: Mock Stream]
mocks/event_generator.py  ───►  In-Memory EventBus  ───►  Sentinel & Intelligence Agents

[Phase 2: Member 1 Production Integration]
Member 1 Digital World (WS / gRPC) ───► Ingestion Adapter ───► In-Memory EventBus ───► Sentinel & Agents
                                                                        ▲
Member 1 Digital World REST APIs   ◄─── Actuator Dispatcher ────────────┘ (Executor Agent)
```

### Transition Steps:
1. **Telemetry Stream Adapter**:
   A WebSocket/gRPC listener (`runtime/adapters/digital_world_adapter.py`) will connect to `DIGITAL_WORLD_WS_STREAM_URL`, deserialize incoming live telemetry into `SystemEvent` models, and publish them onto `EventBus`.
2. **Dependency Graph Service Integration**:
   The `DependencyAgent` will swap local mock graphs for live REST queries against `DIGITAL_WORLD_API_BASE_URL/topology/graph` to query dynamic blast radiuses.
3. **Chaos Injection Listener**:
   Member 1's chaos injection events will be tagged with standard `correlation_id` headers and mapped directly to `SystemEvent` instances.
4. **Remediation Actuator Dispatch**:
   The `ExecutorAgent` will convert planned actions into authenticated HTTP requests dispatched to `DIGITAL_WORLD_API_BASE_URL/actions/execute`.
5. **No Agent Core Code Refactoring**:
   Because all agents consume events through the abstracted `EventBus` and publish structured plans to the `governance` layer, changing the upstream telemetry provider from mock to live Digital World requires **zero modifications** to agent logic.

---

## Testing

Run the automated test suite:

```bash
pytest
```
