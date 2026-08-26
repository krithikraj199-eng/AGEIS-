"""
Unit and Integration Tests for AEGIS Ω OpenTelemetry Distributed Tracing & Trace Reporter.
Tests:
  - Span creation with required fields (incident_id, agent_id, timestamp, status)
  - Unified trace context propagation
  - 13-stage end-to-end trace recording (Sentinel -> ... -> Verifier -> Recovery -> Memory)
  - Chronological trace report generation from real recorded data (observability/trace_report.py)
"""

import asyncio
import subprocess
import sys
from datetime import datetime, timezone

from observability.telemetry import (
    setup_telemetry,
    trace_span,
    trace_agent_span,
    record_pipeline_stage_span,
)
from observability.trace_store import SpanRecord, TraceStore, trace_store
from observability.trace_report import generate_trace_timeline, generate_simple_timeline
from mocks.event_generator import SystemEvent, EventType, Severity
from runtime.main import AgentPipeline


def test_span_recording_with_required_fields():
    """
    Verify every span contains: incident_id, agent_id, timestamp, status.
    """
    store = TraceStore()
    store.clear()

    rec = record_pipeline_stage_span(
        agent_id="Sentinel",
        incident_id="INC-test-telemetry-01",
        status="DETECTED",
        summary="Sentinel detected anomaly",
        attributes={"metric": "latency_ms", "value": 850.0},
    )

    assert rec.incident_id == "INC-test-telemetry-01"
    assert rec.agent_id == "Sentinel"
    assert rec.status == "DETECTED"
    assert rec.summary == "Sentinel detected anomaly"
    assert rec.timestamp != ""
    assert rec.time_formatted != ""


def test_trace_store_chronological_ordering():
    """Verify trace store returns spans in chronological order."""
    store = TraceStore()
    store.clear()

    inc_id = "INC-chrono-order-01"
    stages = [
        ("Sentinel", "DETECTED", "Sentinel detected anomaly"),
        ("Investigator", "STARTED", "Investigator started"),
        ("Evidence", "SUCCESS", "Evidence generated"),
        ("Dependency", "SUCCESS", "Dependency calculated"),
        ("Security", "SUCCESS", "Security classified"),
        ("Root Cause", "SUCCESS", "Root cause diagnosed"),
        ("Planner", "SUCCESS", "Planner formulated plans"),
        ("Counterfactual", "SUCCESS", "Counterfactual simulated safest plan"),
        ("Risk", "SUCCESS", "Risk evaluated gate: AUTO_EXECUTE"),
        ("Executor", "SUCCESS", "Executor executed scale_service"),
        ("Verifier", "SUCCESS", "Verifier SUCCESS"),
        ("Recovery", "SUCCESS", "Recovery confirmed resolved"),
        ("Memory", "SUCCESS", "Memory recorded episodic pattern"),
    ]

    for agent, status, summary in stages:
        store.record_span(
            SpanRecord(
                incident_id=inc_id,
                agent_id=agent,
                span_name=f"agent.{agent.lower()}",
                status=status,
                summary=summary,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

    spans = store.get_trace(inc_id)
    assert len(spans) == 13
    assert spans[0].agent_id == "Sentinel"
    assert spans[-1].agent_id == "Memory"

    # Test report formatting
    report = generate_trace_timeline(spans, inc_id)
    assert inc_id in report
    assert "Sentinel" in report
    assert "Verifier" in report
    assert "Memory" in report

    simple_report = generate_simple_timeline(spans)
    assert "Sentinel detected anomaly" in simple_report
    assert "Verifier SUCCESS" in simple_report


def test_full_pipeline_cascading_failure_trace_generation():
    """
    Execute cascading failure through AgentPipeline and verify complete
    OpenTelemetry trace spans are recorded across all stages.
    """
    async def _test():
        trace_store.clear()
        pipeline = AgentPipeline()
        pipeline.start()

        event = SystemEvent(
            correlation_id="corr-otel-cascade-1",
            asset_id="DATABASE-01",
            event_type=EventType.DATABASE_TIMEOUT,
            severity=Severity.HIGH,
            metrics={"latency_ms": 950.0, "connection_pool_active": 490},
            logs=["CRITICAL connection pool exhaustion on DATABASE-01"],
        )

        summary = await pipeline.execute_incident(event, timeout_seconds=8.0)
        pipeline.stop()

        assert summary.success is True
        inc_id = summary.incident_id

        # Verify real recorded trace from trace_store
        spans = trace_store.get_trace(inc_id)
        assert len(spans) >= 10, f"Expected at least 10 recorded spans, got {len(spans)}"

        recorded_agents = [s.agent_id for s in spans]
        assert "Sentinel" in recorded_agents
        assert "Investigator" in recorded_agents
        assert "Evidence" in recorded_agents
        assert "Dependency" in recorded_agents
        assert "Security" in recorded_agents
        assert "Root Cause" in recorded_agents
        assert "Planner" in recorded_agents
        assert "Counterfactual" in recorded_agents
        assert "Risk" in recorded_agents
        assert "Executor" in recorded_agents
        assert "Verifier" in recorded_agents
        assert "Recovery" in recorded_agents

    asyncio.run(_test())


def test_trace_report_cli_execution():
    """
    Test running observability/trace_report.py CLI script against real trace data.
    """
    # Seed a real trace
    inc_id = "INC-CLI-TEST-001"
    record_pipeline_stage_span("Sentinel", inc_id, "DETECTED", "Sentinel detected anomaly")
    record_pipeline_stage_span("Investigator", inc_id, "STARTED", "Investigator started")
    record_pipeline_stage_span("Verifier", inc_id, "SUCCESS", "Verifier SUCCESS")

    result = subprocess.run(
        [sys.executable, "observability/trace_report.py", inc_id, "--format", "simple"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Sentinel detected anomaly" in result.stdout
    assert "Verifier SUCCESS" in result.stdout
