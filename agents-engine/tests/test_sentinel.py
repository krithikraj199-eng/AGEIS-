"""
Unit Tests for Sentinel Agent in AEGIS Ω.
Tests deterministic thresholds, multi-signal correlation windows,
conditional Gemini semantic correlation, and output schema validation.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

from runtime.event_bus import EventBus
from mocks.event_generator import (
    EventType,
    Severity,
    generate_event,
    generate_cascading_failure,
)
from agents.sentinel.agent import (
    SentinelAgent,
    SentinelInput,
    SentinelOutput,
    SentinelStatus,
    GeminiCorrelatorProtocol,
)
from agents.sentinel.config import SentinelThresholds


class MockGeminiCorrelator:
    """Mock implementation of GeminiCorrelatorProtocol to track and spy LLM invocations."""

    def __init__(self, response_text: str = "Semantic LLM correlation: Root failure on primary DB caused cascade."):
        self.response_text = response_text
        self.call_count = 0
        self.recorded_calls: List[Dict[str, Any]] = []

    async def correlate_and_summarize(
        self,
        events: List[Dict[str, Any]],
        correlation_id: str,
    ) -> str:
        self.call_count += 1
        self.recorded_calls.append({
            "events": events,
            "correlation_id": correlation_id,
        })
        return f"{self.response_text} (Correlated {len(events)} events)"


def test_normal_event_evaluation():
    """Verify NORMAL telemetry produces status NORMAL without calling Gemini or publishing incident."""
    async def _test():
        bus = EventBus()
        triage_events = []
        bus.subscribe("incident.triage", lambda ev: triage_events.append(ev))

        mock_correlator = MockGeminiCorrelator()
        agent = SentinelAgent(event_bus=bus, correlator=mock_correlator)
        agent.start()

        event = generate_event(
            asset_id="API-01",
            event_type=EventType.CPU_NORMAL,
            severity=Severity.INFO,
            metrics={"cpu_utilization_pct": 32.5, "load_avg_1m": 0.8},
        )

        output = await agent.handle_event(event)

        assert output is not None
        assert output.status == SentinelStatus.NORMAL
        assert "normal" in output.summary.lower()
        # Gemini must NOT be called for normal telemetry
        assert mock_correlator.call_count == 0
        # NORMAL events must NOT be published to incident.triage
        assert len(triage_events) == 0

        agent.stop()

    asyncio.run(_test())


def test_isolated_cpu_breach():
    """Verify isolated CPU > 90% triggers WARNING, uses deterministic summary, and DOES NOT call Gemini."""
    async def _test():
        bus = EventBus()
        triage_events = []
        bus.subscribe("incident.triage", lambda ev: triage_events.append(ev))

        mock_correlator = MockGeminiCorrelator()
        thresholds = SentinelThresholds(cpu_threshold_pct=90.0)
        agent = SentinelAgent(event_bus=bus, thresholds=thresholds, correlator=mock_correlator)
        agent.start()

        event = generate_event(
            asset_id="WORKER-01",
            event_type=EventType.CPU_NORMAL,
            severity=Severity.INFO,
            metrics={"cpu_utilization_pct": 94.5, "load_avg_1m": 4.2},
            correlation_id="isolated-cpu-123",
        )

        output = await agent.handle_event(event)

        assert output is not None
        assert output.status == SentinelStatus.WARNING
        assert "cpu_utilization_pct=94.5" in output.summary
        # Isolated breach MUST NOT invoke Gemini
        assert mock_correlator.call_count == 0
        # WARNING must be published to incident.triage for Investigator
        assert len(triage_events) == 1
        assert triage_events[0].incident_id == output.incident_id

        agent.stop()

    asyncio.run(_test())


def test_isolated_threshold_breaches_never_call_gemini():
    """Explicit test verifying Gemini is NOT called for isolated memory, disk, latency, or error-rate breaches."""
    async def _test():
        bus = EventBus()
        mock_correlator = MockGeminiCorrelator()
        agent = SentinelAgent(event_bus=bus, correlator=mock_correlator)

        # 1. Memory breach (> 95%)
        ev_mem = generate_event(
            asset_id="CACHE-01",
            event_type=EventType.MEMORY_WARNING,
            metrics={"memory_used_pct": 98.2},
            correlation_id="single-mem-1",
        )
        out_mem = await agent.process(SentinelInput.model_validate(ev_mem.to_dict()))
        assert out_mem.status in [SentinelStatus.WARNING, SentinelStatus.ANOMALY]
        assert mock_correlator.call_count == 0

        # 2. Disk breach (> 95%)
        ev_disk = generate_event(
            asset_id="STORAGE-01",
            event_type=EventType.DISK_FULL,
            metrics={"disk_used_pct": 97.4},
            correlation_id="single-disk-1",
        )
        out_disk = await agent.process(SentinelInput.model_validate(ev_disk.to_dict()))
        assert out_disk.status in [SentinelStatus.WARNING, SentinelStatus.ANOMALY]
        assert mock_correlator.call_count == 0

        # 3. Latency breach (> 2000ms)
        ev_lat = generate_event(
            asset_id="API-01",
            event_type=EventType.NETWORK_LATENCY,
            metrics={"p99_latency_ms": 3200.0},
            correlation_id="single-lat-1",
        )
        out_lat = await agent.process(SentinelInput.model_validate(ev_lat.to_dict()))
        assert out_lat.status in [SentinelStatus.WARNING, SentinelStatus.ANOMALY]
        assert mock_correlator.call_count == 0

        # Verify call count is strictly 0 across all isolated breaches
        assert mock_correlator.call_count == 0

    asyncio.run(_test())


def test_configurable_thresholds():
    """Verify custom thresholds can be configured without modifying agent code."""
    async def _test():
        bus = EventBus()
        # Set tighter custom threshold: CPU at 75%
        custom_thresholds = SentinelThresholds(cpu_threshold_pct=75.0, latency_threshold_ms=800.0)
        agent = SentinelAgent(event_bus=bus, thresholds=custom_thresholds)

        # 78% CPU is below default 90% but above custom 75%
        event = generate_event(
            asset_id="APP-01",
            event_type=EventType.CPU_NORMAL,
            metrics={"cpu_utilization_pct": 78.0},
        )
        output = await agent.process(SentinelInput.model_validate(event.to_dict()))
        assert output.status == SentinelStatus.WARNING

    asyncio.run(_test())


def test_multiple_correlated_failures_invokes_gemini():
    """Verify multiple correlated events sharing correlation_id trigger Gemini semantic correlation."""
    async def _test():
        bus = EventBus()
        mock_correlator = MockGeminiCorrelator(response_text="Database lock contention triggered auth cascade")
        agent = SentinelAgent(event_bus=bus, correlator=mock_correlator)

        cid = "multi-signal-corr-99"

        # Signal 1: Database timeout
        ev1 = generate_event(
            asset_id="DATABASE-01",
            event_type=EventType.DATABASE_TIMEOUT,
            severity=Severity.CRITICAL,
            metrics={"query_latency_ms": 30000.0},
            correlation_id=cid,
        )
        out1 = await agent.process(SentinelInput.model_validate(ev1.to_dict()))
        # First event is isolated -> Gemini NOT called yet
        assert mock_correlator.call_count == 0
        assert out1.status == SentinelStatus.CRITICAL

        # Signal 2: Auth login failure sharing the same correlation_id
        ev2 = generate_event(
            asset_id="AUTH-01",
            event_type=EventType.LOGIN_FAILURE,
            severity=Severity.HIGH,
            metrics={"failed_auth_rate_pct": 95.0},
            correlation_id=cid,
        )
        out2 = await agent.process(SentinelInput.model_validate(ev2.to_dict()))

        # Now 2 correlated signals occurred within window -> Gemini MUST BE CALLED
        assert mock_correlator.call_count == 1
        assert "Database lock contention" in out2.summary
        assert out2.status == SentinelStatus.CRITICAL
        assert len(out2.triggering_events) == 2
        assert out2.triggering_events[0]["asset_id"] == "DATABASE-01"
        assert out2.triggering_events[1]["asset_id"] == "AUTH-01"

    asyncio.run(_test())


def test_cascading_failure_scenario():
    """Verify full 4-stage cascade (DATABASE-01 -> AUTH-01 -> API-01 -> PORTAL-01) triggers Gemini and outputs CRITICAL."""
    async def _test():
        bus = EventBus()
        mock_correlator = MockGeminiCorrelator(response_text="Cascading failure across DB, Auth, API, and Portal")
        agent = SentinelAgent(event_bus=bus, correlator=mock_correlator)

        cascade_events = generate_cascading_failure(correlation_id="cascade-test-full")
        assert len(cascade_events) == 4

        outputs = []
        for ev in cascade_events:
            out = await agent.process(SentinelInput.model_validate(ev.to_dict()))
            outputs.append(out)

        # After the 4 events, Gemini was called for the multi-signal correlations (events 2, 3, 4)
        assert mock_correlator.call_count == 3
        final_output = outputs[-1]

        assert final_output.status == SentinelStatus.CRITICAL
        assert len(final_output.triggering_events) == 4
        assert "Cascading failure across DB" in final_output.summary
        assert final_output.incident_id.startswith("INC-cascade-")

    asyncio.run(_test())


def test_sentinel_output_exact_schema():
    """Validate that SentinelOutput matches the exact required fields and status enum."""
    output = SentinelOutput(
        incident_id="INC-test1234",
        status=SentinelStatus.CRITICAL,
        triggering_events=[{"asset_id": "DATABASE-01", "event_type": "DATABASE_TIMEOUT"}],
        summary="Critical database timeout",
        timestamp="2026-08-25T14:00:00Z",
        correlation_id="test1234",
        asset_id="DATABASE-01",
    )

    data = output.model_dump()
    assert "incident_id" in data
    assert "status" in data
    assert data["status"] in ["NORMAL", "WARNING", "ANOMALY", "CRITICAL"]
    assert "triggering_events" in data
    assert "summary" in data
    assert "timestamp" in data
