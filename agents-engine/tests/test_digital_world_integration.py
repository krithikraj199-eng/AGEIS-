"""
Integration Tests for Member 1's Digital World API Integration.
Verifies all 6 functional APIs:
1. Event stream (timestamp, asset_id, event_type, severity, metrics, source, correlation_id)
2. Metrics API (get_current_metric, get_historical_metrics)
3. Dependency graph API (get_dependencies, get_dependents)
4. History API (search_similar_incidents)
5. Action API (restart, scale, rollback, clear_cache, quarantine, restore_config)
6. Chaos injection & test hooks (inject_fault, inject_cascading_failure)
"""

import asyncio
from datetime import datetime, timezone

from digital_world.client import DigitalWorldClient, get_digital_world_client
from digital_world.models import (
    DigitalWorldEvent,
    DigitalWorldEventType,
    DigitalWorldSeverity,
    HistoricalIncidentRecord,
)
from runtime.event_bus import EventBus
from runtime.main import AgentPipeline, PipelineExecutionSummary
from tools.registry import ToolRegistry
from governance.guardrails import sanitize_untrusted_content


def test_event_stream_schema():
    """1. Test Event stream schema conformity."""
    dw = DigitalWorldClient()
    ev = dw.generate_event(
        asset_id="DATABASE-01",
        event_type="DATABASE_TIMEOUT",
        severity="CRITICAL",
        metrics={"latency_ms": 850.0, "query_latency_ms": 32000.0},
        source="digital_world_sensor",
        correlation_id="corr-dw-test-01",
    )

    assert isinstance(ev, DigitalWorldEvent)
    assert ev.timestamp is not None
    assert ev.asset_id == "DATABASE-01"
    assert ev.event_type == "DATABASE_TIMEOUT"
    assert ev.severity == "CRITICAL"
    assert ev.metrics["latency_ms"] == 850.0
    assert ev.source == "digital_world_sensor"
    assert ev.correlation_id == "corr-dw-test-01"

    d = ev.to_dict()
    assert "timestamp" in d
    assert "asset_id" in d
    assert "event_type" in d
    assert "severity" in d
    assert "metrics" in d
    assert "source" in d
    assert "correlation_id" in d


def test_metrics_api():
    """2. Test Metrics API: get_current_metric and get_historical_metrics."""
    dw = DigitalWorldClient()

    # Query current metric
    current_latency = dw.get_current_metric("DATABASE-01", "latency_ms")
    assert current_latency == 850.0

    # Query historical metrics (15-minute window)
    hist_series = dw.get_historical_metrics("DATABASE-01", "latency_ms", window_minutes=10)
    assert isinstance(hist_series, list)
    assert len(hist_series) == 10
    for pt in hist_series:
        assert "timestamp" in pt
        assert "value" in pt
        assert "metric" in pt
        assert pt["metric"] == "latency_ms"
        assert pt["asset_id"] == "DATABASE-01"

    # Test metric updates
    dw.set_metric("DATABASE-01", "latency_ms", 110.0)
    assert dw.get_current_metric("DATABASE-01", "latency_ms") == 110.0


def test_dependency_graph_api():
    """3. Test Dependency Graph API: get_dependencies and get_dependents."""
    dw = DigitalWorldClient()

    # Upstream dependencies: What does PORTAL-01 depend on?
    portal_deps = dw.get_dependencies("PORTAL-01", recursive=True)
    assert "API-01" in portal_deps
    assert "AUTH-01" in portal_deps
    assert "DATABASE-01" in portal_deps

    # Downstream dependents: What depends on DATABASE-01?
    db_dependents = dw.get_dependents("DATABASE-01", recursive=True)
    assert "AUTH-01" in db_dependents
    assert "API-01" in db_dependents
    assert "PORTAL-01" in db_dependents

    # Direct non-recursive dependencies
    db_direct = dw.get_dependents("DATABASE-01", recursive=False)
    assert "AUTH-01" in db_direct
    assert "API-01" not in db_direct


def test_history_api():
    """4. Test History API: search_similar_incidents by signature."""
    dw = DigitalWorldClient()

    # Search for database timeout incident
    results = dw.search_similar_incidents("DATABASE-01:DATABASE_TIMEOUT", limit=2)
    assert len(results) >= 1
    first = results[0]
    assert first["affected_asset"] == "DATABASE-01"
    assert "connection pool" in first["root_cause"].lower()
    assert first["resolution"] != ""

    # Test guardrail sanitization on history retrieved from Digital World
    sanitized = sanitize_untrusted_content(first["root_cause"])
    assert "<untrusted_data>" in sanitized.wrapped_data_block
    assert sanitized.has_injection_risk is False


def test_action_api_all_six_tools():
    """5. Test Action API: execution of all 6 operational tools."""
    async def _test():
        dw = DigitalWorldClient()

        # 1. restart_service
        res_restart = await dw.restart_service("DATABASE-01", grace_period_sec=10)
        assert res_restart["status"] == "SUCCESS"
        assert res_restart["action"] == "restart_service"
        assert dw.get_current_metric("DATABASE-01", "latency_ms") == 110.0

        # 2. scale_service
        res_scale = await dw.scale_service("AUTH-01", factor=2.0, replicas=4)
        assert res_scale["status"] == "SUCCESS"
        assert res_scale["action"] == "scale_service"

        # 3. rollback_deployment
        res_rollback = await dw.rollback_deployment("AUTH-01", target_version="v1.14.0")
        assert res_rollback["status"] == "SUCCESS"
        assert res_rollback["action"] == "rollback_deployment"

        # 4. clear_cache
        res_clear = await dw.clear_cache("API-01", cache_pattern="session:*")
        assert res_clear["status"] == "SUCCESS"
        assert res_clear["action"] == "clear_cache"

        # 5. quarantine_asset
        res_quarantine = await dw.quarantine_asset("WORKER-01", reason="malicious_egress")
        assert res_quarantine["status"] == "SUCCESS"
        assert res_quarantine["action"] == "quarantine_asset"

        # 6. restore_configuration
        res_restore = await dw.restore_configuration("PORTAL-01", config_snapshot_id="SNAP-PORTAL-01")
        assert res_restore["status"] == "SUCCESS"
        assert res_restore["action"] == "restore_configuration"

        # Confirm 6 actions recorded in history
        assert len(dw.actions.action_history) == 6

    asyncio.run(_test())


def test_chaos_injection_and_full_pipeline():
    """6. Test Chaos Injection & Full Pipeline execution against live Digital World."""
    async def _test():
        dw = DigitalWorldClient()
        bus = EventBus()
        pipeline = AgentPipeline(event_bus=bus)
        pipeline.executor.client = dw
        pipeline.executor.registry = ToolRegistry(client=dw)
        pipeline.start()

        # Inject 4-tier cascading failure
        cascade_events = dw.inject_cascading_failure(correlation_id="dw-cascade-live")
        assert len(cascade_events) == 4
        assert cascade_events[0].asset_id == "DATABASE-01"
        assert cascade_events[1].asset_id == "AUTH-01"
        assert cascade_events[2].asset_id == "API-01"
        assert cascade_events[3].asset_id == "PORTAL-01"

        # Run through pipeline
        for ev in cascade_events:
            summary: PipelineExecutionSummary = await pipeline.execute_incident(ev, timeout_seconds=8.0)
            assert summary.success is True
            assert summary.final_status == "RESOLVED"

        pipeline.stop()

    asyncio.run(_test())
