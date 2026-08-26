"""
Tests for In-Memory EventBus.
"""

import asyncio
from runtime.event_bus import EventBus
from mocks.event_generator import generate_event, EventType, Severity


def test_event_bus_subscribe_and_publish():
    async def _test():
        bus = EventBus()
        received = []

        async def sample_handler(event):
            received.append(event)

        bus.subscribe("telemetry.database_timeout", sample_handler)

        event = generate_event(asset_id="DATABASE-01", event_type=EventType.DATABASE_TIMEOUT)
        await bus.publish("telemetry.database_timeout", event)

        assert len(received) == 1
        assert received[0].asset_id == "DATABASE-01"
        assert received[0].event_type == EventType.DATABASE_TIMEOUT

    asyncio.run(_test())


def test_event_bus_wildcard_subscription():
    async def _test():
        bus = EventBus()
        received = []

        def sync_handler(event):
            received.append(event)

        bus.subscribe("*", sync_handler)

        e1 = generate_event(asset_id="API-01", event_type=EventType.SERVICE_CRASH)
        e2 = generate_event(asset_id="AUTH-01", event_type=EventType.LOGIN_FAILURE)

        await bus.publish("telemetry.service_crash", e1)
        await bus.publish("telemetry.login_failure", e2)

        assert len(received) == 2
        assert received[0].asset_id == "API-01"
        assert received[1].asset_id == "AUTH-01"

    asyncio.run(_test())


def test_event_bus_error_isolation_and_dlq():
    async def _test():
        bus = EventBus(enable_dlq=True)

        def faulty_handler(event):
            raise ValueError("Handler deliberate failure")

        bus.subscribe("test.topic", faulty_handler)
        event = generate_event(asset_id="TEST-01", event_type=EventType.CPU_NORMAL)

        # Should not raise exception
        await bus.publish("test.topic", event)

        assert len(bus.dead_letter_queue) == 1
        assert bus.dead_letter_queue[0].error_message == "Handler deliberate failure"

    asyncio.run(_test())
