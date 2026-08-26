"""
Tests for Mock Event Generator and Cascading Failure Scenario.
"""

import asyncio
from mocks.event_generator import (
    EventType,
    Severity,
    SystemEvent,
    generate_event,
    generate_cascading_failure,
    EventGenerator,
)
from runtime.event_bus import EventBus


def test_system_event_schema_compliance():
    event = generate_event(
        asset_id="DATABASE-01",
        event_type=EventType.DATABASE_TIMEOUT,
        severity=Severity.CRITICAL,
        metrics={"latency": 1200},
        source="unit_test",
        correlation_id="test-corr-123",
    )

    data = event.to_dict()
    assert "timestamp" in data
    assert data["asset_id"] == "DATABASE-01"
    assert data["event_type"] == "DATABASE_TIMEOUT"
    assert data["severity"] == "CRITICAL"
    assert data["metrics"] == {"latency": 1200}
    assert data["source"] == "unit_test"
    assert data["correlation_id"] == "test-corr-123"


def test_all_supported_event_types():
    expected_types = [
        "CPU_NORMAL",
        "MEMORY_WARNING",
        "DISK_FULL",
        "NETWORK_LATENCY",
        "DATABASE_TIMEOUT",
        "LOGIN_FAILURE",
        "SERVICE_CRASH",
        "DEPLOYMENT_CHANGE",
        "SECURITY_ALERT",
    ]
    for et in expected_types:
        ev = generate_event(asset_id="ASSET-X", event_type=et)
        assert ev.event_type.value == et
        assert isinstance(ev.metrics, dict)
        assert len(ev.metrics) > 0


def test_cascading_failure_sequence():
    events = generate_cascading_failure(correlation_id="cascade-test-123")
    assert len(events) == 4

    # Verify exact chain: DATABASE-01 -> AUTH-01 -> API-01 -> PORTAL-01
    assert events[0].asset_id == "DATABASE-01"
    assert events[0].event_type == EventType.DATABASE_TIMEOUT

    assert events[1].asset_id == "AUTH-01"
    assert events[1].event_type == EventType.LOGIN_FAILURE

    assert events[2].asset_id == "API-01"
    assert events[2].event_type == EventType.SERVICE_CRASH

    assert events[3].asset_id == "PORTAL-01"
    assert events[3].event_type == EventType.NETWORK_LATENCY

    # Ensure all events share the exact same correlation_id
    for ev in events:
        assert ev.correlation_id == "cascade-test-123"


def test_event_generator_run_cascading_failure():
    async def _test():
        bus = EventBus()
        received_events = []

        bus.subscribe("telemetry.*", lambda ev: received_events.append(ev))

        generator = EventGenerator(event_bus=bus)
        emitted = await generator.run_cascading_failure(delay_seconds=0.0)

        assert len(emitted) == 4
        assert len(received_events) == 4

    asyncio.run(_test())
