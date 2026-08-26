"""
Mock Event Generator for AEGIS Ω Intelligence Engine.
Simulates Digital World telemetry streams, system anomalies, and cascading failure scenarios.
"""

import argparse
import asyncio
import json
import random
import sys
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field

# Ensure runtime package can be imported when running as script
try:
    from runtime.event_bus import EventBus, get_event_bus
except ImportError:
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from runtime.event_bus import EventBus, get_event_bus


class EventType(str, Enum):
    """Supported event types in the AEGIS Ω telemetry schema."""
    CPU_NORMAL = "CPU_NORMAL"
    MEMORY_WARNING = "MEMORY_WARNING"
    DISK_FULL = "DISK_FULL"
    NETWORK_LATENCY = "NETWORK_LATENCY"
    DATABASE_TIMEOUT = "DATABASE_TIMEOUT"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    SERVICE_CRASH = "SERVICE_CRASH"
    DEPLOYMENT_CHANGE = "DEPLOYMENT_CHANGE"
    SECURITY_ALERT = "SECURITY_ALERT"


class Severity(str, Enum):
    """Event severity levels."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SystemEvent(BaseModel):
    """
    Standard event schema for all telemetry and incident events in AEGIS Ω.
    """
    timestamp: str = Field(
        description="ISO 8601 UTC timestamp of the event",
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    asset_id: str = Field(
        description="Unique identifier of the target infrastructure asset or service",
    )
    event_type: EventType = Field(
        description="Classified system event type",
    )
    severity: Severity = Field(
        description="Severity classification",
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value metrics snapshot associated with the event",
    )
    source: str = Field(
        default="mock_event_generator",
        description="Originating subsystem, agent, or telemetry collector",
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID linking related events across failure cascades",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to standard dictionary matching required schema."""
        return self.model_dump()

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def get_default_metrics_for_type(event_type: EventType) -> Dict[str, Any]:
    """Generate realistic default metric payloads for a given event type."""
    match event_type:
        case EventType.CPU_NORMAL:
            return {
                "cpu_utilization_pct": round(random.uniform(15.0, 45.0), 2),
                "load_avg_1m": round(random.uniform(0.5, 1.8), 2),
                "temperature_celsius": round(random.uniform(40.0, 55.0), 1),
            }
        case EventType.MEMORY_WARNING:
            return {
                "memory_used_pct": round(random.uniform(85.0, 93.0), 2),
                "swap_used_pct": round(random.uniform(40.0, 65.0), 2),
                "oom_kills_count": 0,
            }
        case EventType.DISK_FULL:
            return {
                "disk_used_pct": round(random.uniform(96.0, 99.8), 2),
                "available_space_mb": round(random.uniform(50.0, 250.0), 1),
                "iops_write_queued": random.randint(120, 450),
            }
        case EventType.NETWORK_LATENCY:
            return {
                "p99_latency_ms": round(random.uniform(450.0, 2800.0), 2),
                "packet_loss_pct": round(random.uniform(3.5, 18.0), 2),
                "active_connections": random.randint(1200, 3500),
            }
        case EventType.DATABASE_TIMEOUT:
            return {
                "query_latency_ms": round(random.uniform(15000.0, 45000.0), 2),
                "connection_pool_usage_pct": 100.0,
                "deadlocks_detected": random.randint(2, 8),
                "active_connections": 500,
            }
        case EventType.LOGIN_FAILURE:
            return {
                "failed_auth_rate_pct": round(random.uniform(80.0, 99.5), 2),
                "db_connection_errors": random.randint(400, 1500),
                "auth_latency_ms": round(random.uniform(5000.0, 12000.0), 2),
            }
        case EventType.SERVICE_CRASH:
            return {
                "uptime_seconds": 0,
                "crash_exit_code": 137,
                "http_5xx_rate_pct": 100.0,
                "restart_attempt_count": random.randint(1, 5),
            }
        case EventType.DEPLOYMENT_CHANGE:
            return {
                "previous_version": "v1.14.2",
                "deployed_version": "v1.15.0-rc.1",
                "diff_lines_changed": 482,
                "deployed_by": "ci-cd-bot",
            }
        case EventType.SECURITY_ALERT:
            return {
                "failed_ssh_attempts_1m": random.randint(50, 400),
                "source_ip_reputation_score": 0.94,
                "cve_identifier": "CVE-2026-9912",
                "mitre_technique": "T1110.001",
            }


def generate_event(
    asset_id: str,
    event_type: EventType | str,
    severity: Optional[Severity | str] = None,
    metrics: Optional[Dict[str, Any]] = None,
    source: str = "mock_event_generator",
    correlation_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> SystemEvent:
    """Helper function to create a validated SystemEvent."""
    if isinstance(event_type, str):
        event_type = EventType(event_type)

    if severity is None:
        # Default severity mapping
        severity_map = {
            EventType.CPU_NORMAL: Severity.INFO,
            EventType.MEMORY_WARNING: Severity.MEDIUM,
            EventType.DISK_FULL: Severity.HIGH,
            EventType.NETWORK_LATENCY: Severity.MEDIUM,
            EventType.DATABASE_TIMEOUT: Severity.CRITICAL,
            EventType.LOGIN_FAILURE: Severity.HIGH,
            EventType.SERVICE_CRASH: Severity.CRITICAL,
            EventType.DEPLOYMENT_CHANGE: Severity.INFO,
            EventType.SECURITY_ALERT: Severity.HIGH,
        }
        severity = severity_map.get(event_type, Severity.MEDIUM)
    elif isinstance(severity, str):
        severity = Severity(severity)

    metrics_payload = metrics if metrics is not None else get_default_metrics_for_type(event_type)

    return SystemEvent(
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        asset_id=asset_id,
        event_type=event_type,
        severity=severity,
        metrics=metrics_payload,
        source=source,
        correlation_id=correlation_id or str(uuid.uuid4()),
    )


def generate_cascading_failure(
    correlation_id: Optional[str] = None,
) -> List[SystemEvent]:
    """
    Generate the classic cascading failure scenario on demand:
        DATABASE-01 (DATABASE_TIMEOUT)
            ↓
        AUTH-01 (LOGIN_FAILURE)
            ↓
        API-01 (SERVICE_CRASH)
            ↓
        PORTAL-01 (NETWORK_LATENCY / SERVICE_CRASH)

    Returns the ordered list of 4 correlated failure events.
    """
    cid = correlation_id or f"cascade-{uuid.uuid4().hex[:8]}"
    events: List[SystemEvent] = []

    # Step 1: DATABASE-01 suffers database timeout / pool exhaustion
    events.append(
        generate_event(
            asset_id="DATABASE-01",
            event_type=EventType.DATABASE_TIMEOUT,
            severity=Severity.CRITICAL,
            metrics={
                "query_latency_ms": 32400.0,
                "connection_pool_usage_pct": 100.0,
                "active_connections": 500,
                "deadlocks": 4,
                "db_state": "UNRESPONSIVE",
            },
            source="db_sentinel_collector",
            correlation_id=cid,
        )
    )

    # Step 2: AUTH-01 cannot verify credentials because DB timed out -> LOGIN_FAILURE
    events.append(
        generate_event(
            asset_id="AUTH-01",
            event_type=EventType.LOGIN_FAILURE,
            severity=Severity.HIGH,
            metrics={
                "failed_auth_rate_pct": 98.6,
                "db_connection_errors": 1420,
                "auth_latency_ms": 11500.0,
                "downstream_dependency": "DATABASE-01",
            },
            source="auth_service_sentinel",
            correlation_id=cid,
        )
    )

    # Step 3: API-01 gets saturated waiting for auth tokens and crashes -> SERVICE_CRASH
    events.append(
        generate_event(
            asset_id="API-01",
            event_type=EventType.SERVICE_CRASH,
            severity=Severity.CRITICAL,
            metrics={
                "uptime_seconds": 0,
                "crash_exit_code": 137,
                "http_5xx_rate_pct": 100.0,
                "failed_requests_per_sec": 8450,
                "downstream_dependency": "AUTH-01",
            },
            source="api_gateway_monitor",
            correlation_id=cid,
        )
    )

    # Step 4: PORTAL-01 user-facing UI portal fails completely
    events.append(
        generate_event(
            asset_id="PORTAL-01",
            event_type=EventType.NETWORK_LATENCY,
            severity=Severity.HIGH,
            metrics={
                "gateway_timeout_pct": 100.0,
                "user_facing_error_rate_pct": 100.0,
                "p99_latency_ms": 30000.0,
                "downstream_dependency": "API-01",
            },
            source="edge_ingress_sentinel",
            correlation_id=cid,
        )
    )

    return events


class EventGenerator:
    """
    Event Generator engine that can produce individual events, continuous random telemetry,
    or cascading failure simulations directly into memory or an EventBus.
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus or get_event_bus()

    async def emit(self, event: SystemEvent) -> None:
        """Publish an event to the EventBus."""
        topic = f"telemetry.{event.event_type.value.lower()}"
        await self.event_bus.publish(topic, event)
        # Also publish on wildcards
        await self.event_bus.publish("telemetry.*", event)
        await self.event_bus.publish(f"asset.{event.asset_id}", event)

    async def run_cascading_failure(
        self,
        delay_seconds: float = 0.5,
        correlation_id: Optional[str] = None,
        callback: Optional[Any] = None,
    ) -> List[SystemEvent]:
        """
        Execute and publish the cascading failure scenario:
        DATABASE-01 -> AUTH-01 -> API-01 -> PORTAL-01 with inter-event delays.
        """
        events = generate_cascading_failure(correlation_id=correlation_id)
        for event in events:
            await self.emit(event)
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
        return events

    async def stream_random_events(
        self,
        count: int = 10,
        interval_seconds: float = 0.5,
        correlation_id: Optional[str] = None,
    ) -> AsyncGenerator[SystemEvent, None]:
        """Generate a stream of randomized system events."""
        assets = ["DATABASE-01", "AUTH-01", "API-01", "PORTAL-01", "CACHE-01", "PAYMENT-01", "WORKER-01"]
        cid = correlation_id or str(uuid.uuid4())

        for _ in range(count):
            asset_id = random.choice(assets)
            event_type = random.choice(list(EventType))
            event = generate_event(asset_id=asset_id, event_type=event_type, correlation_id=cid)
            await self.emit(event)
            yield event
            if interval_seconds > 0:
                await asyncio.sleep(interval_seconds)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def main():
    """Command-line interface to test and run the mock event generator."""
    parser = argparse.ArgumentParser(
        description="AEGIS Ω — Mock Event Generator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate cascading failure scenario to stdout:
  python mocks/event_generator.py --scenario cascade

  # Generate 5 random events:
  python mocks/event_generator.py --scenario random --count 5

  # Run cascade with 1.0s delay between events:
  python mocks/event_generator.py --scenario cascade --delay 1.0
        """,
    )
    parser.add_argument(
        "--scenario",
        choices=["cascade", "random", "single"],
        default="cascade",
        help="Simulation scenario to execute (default: cascade)",
    )
    parser.add_argument(
        "--event-type",
        choices=[e.value for e in EventType],
        default="DATABASE_TIMEOUT",
        help="Event type for 'single' scenario (default: DATABASE_TIMEOUT)",
    )
    parser.add_argument(
        "--asset-id",
        default="DATABASE-01",
        help="Asset ID for 'single' scenario (default: DATABASE-01)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of events for 'random' scenario (default: 5)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Delay in seconds between simulated events (default: 0.3)",
    )
    parser.add_argument(
        "--correlation-id",
        type=str,
        default=None,
        help="Custom correlation ID to attach to generated events",
    )

    args = parser.parse_args()

    async def _run():
        generator = EventGenerator()

        print("=" * 78)
        print("  AEGIS OMEGA -- Telemetry & Chaos Event Stream Simulation")
        print("=" * 78)

        if args.scenario == "cascade":
            print(f"[*] Triggering Cascading Failure: DATABASE-01 -> AUTH-01 -> API-01 -> PORTAL-01")
            print(f"[*] Inter-event delay: {args.delay}s\n")

            async def print_event(ev: SystemEvent):
                print(f"[{ev.timestamp}] [SEVERITY: {ev.severity.value:<8}] [{ev.asset_id:<12}] -> {ev.event_type.value}")
                print(f"    Correlation ID: {ev.correlation_id}")
                print(f"    Metrics: {json.dumps(ev.metrics)}")
                print("-" * 78)

            await generator.run_cascading_failure(
                delay_seconds=args.delay,
                correlation_id=args.correlation_id,
                callback=print_event,
            )
            print("[+] Cascading failure sequence completed successfully.")

        elif args.scenario == "random":
            print(f"[*] Emitting {args.count} randomized system events...")
            async for ev in generator.stream_random_events(count=args.count, interval_seconds=args.delay, correlation_id=args.correlation_id):
                print(f"[{ev.timestamp}] [{ev.severity.value:<8}] [{ev.asset_id:<12}] {ev.event_type.value} -> metrics: {json.dumps(ev.metrics)}")

        elif args.scenario == "single":
            ev = generate_event(
                asset_id=args.asset_id,
                event_type=EventType(args.event_type),
                correlation_id=args.correlation_id,
            )
            await generator.emit(ev)
            print(ev.to_json(indent=2))

    asyncio.run(_run())


if __name__ == "__main__":
    main()
