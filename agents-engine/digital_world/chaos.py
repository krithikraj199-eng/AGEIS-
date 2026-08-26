"""
Chaos Injection & Test Hooks for Digital World Environment.
Allows deterministic fault injection and cascading failure simulation.
"""

from datetime import datetime, timezone
import random
from typing import Any, Dict, List, Optional
import uuid

from .models import DigitalWorldEvent, DigitalWorldEventType, DigitalWorldSeverity


class ChaosEngine:
    """
    Chaos Injection and Test Hook engine for Member 1's Digital World environment.
    """

    def __init__(self, metrics_api=None):
        self.metrics_api = metrics_api
        self.injected_faults: List[Dict[str, Any]] = []

    def inject_fault(
        self,
        asset_id: str,
        fault_type: str,
        severity: str = "CRITICAL",
        metrics_override: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        source: str = "digital_world_sensor",
    ) -> DigitalWorldEvent:
        """Inject an individual fault into an infrastructure asset."""
        corr_id = correlation_id or f"chaos-{uuid.uuid4().hex[:8]}"
        metrics = metrics_override or self._get_fault_metrics(fault_type)

        event = DigitalWorldEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            asset_id=asset_id,
            event_type=fault_type,
            severity=severity,
            metrics=metrics,
            source=source,
            correlation_id=corr_id,
        )

        # Update metrics API if attached
        if self.metrics_api:
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    self.metrics_api.update_metric(asset_id, k, float(v))

        self.injected_faults.append({
            "asset_id": asset_id,
            "fault_type": fault_type,
            "severity": severity,
            "correlation_id": corr_id,
            "timestamp": event.timestamp,
        })
        return event

    def inject_cascading_failure(
        self,
        correlation_id: Optional[str] = None,
        root_asset_id: str = "DATABASE-01",
    ) -> List[DigitalWorldEvent]:
        """
        Simulate a 4-tier cascading failure:
        DATABASE-01 -> AUTH-01 -> API-01 -> PORTAL-01
        """
        corr_id = correlation_id or f"cascade-dw-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        events = [
            DigitalWorldEvent(
                timestamp=now,
                asset_id="DATABASE-01",
                event_type="DATABASE_TIMEOUT",
                severity="CRITICAL",
                metrics={
                    "query_latency_ms": 32000.0,
                    "latency_ms": 850.0,
                    "connection_pool_usage_pct": 100.0,
                    "deadlocks_detected": 4,
                    "active_connections": 500,
                },
                source="digital_world_chaos_engine",
                correlation_id=corr_id,
            ),
            DigitalWorldEvent(
                timestamp=now,
                asset_id="AUTH-01",
                event_type="LOGIN_FAILURE",
                severity="HIGH",
                metrics={
                    "auth_latency_ms": 1250.0,
                    "latency_ms": 420.0,
                    "failed_auth_rate_pct": 92.5,
                    "active_sessions": 25,
                },
                source="digital_world_chaos_engine",
                correlation_id=corr_id,
            ),
            DigitalWorldEvent(
                timestamp=now,
                asset_id="API-01",
                event_type="SERVICE_CRASH",
                severity="CRITICAL",
                metrics={
                    "http_5xx_rate_pct": 98.0,
                    "latency_ms": 310.0,
                    "crash_exit_code": 137,
                    "uptime_seconds": 0,
                },
                source="digital_world_chaos_engine",
                correlation_id=corr_id,
            ),
            DigitalWorldEvent(
                timestamp=now,
                asset_id="PORTAL-01",
                event_type="NETWORK_LATENCY",
                severity="CRITICAL",
                metrics={
                    "p99_latency_ms": 28500.0,
                    "portal_latency_ms": 280.0,
                    "gateway_timeout_pct": 100.0,
                    "active_users_dropped_pct": 95.0,
                },
                source="digital_world_chaos_engine",
                correlation_id=corr_id,
            ),
        ]

        if self.metrics_api:
            for ev in events:
                for k, v in ev.metrics.items():
                    if isinstance(v, (int, float)):
                        self.metrics_api.update_metric(ev.asset_id, k, float(v))

        return events

    def reset_environment(self) -> None:
        """Clear injected faults and reset state."""
        self.injected_faults.clear()

    def _get_fault_metrics(self, fault_type: str) -> Dict[str, Any]:
        match fault_type:
            case "DATABASE_TIMEOUT":
                return {"query_latency_ms": 35000.0, "connection_pool_usage_pct": 100.0, "latency_ms": 850.0}
            case "LOGIN_FAILURE":
                return {"failed_auth_rate_pct": 94.0, "memory_used_pct": 92.0, "latency_ms": 420.0}
            case "SERVICE_CRASH":
                return {"http_5xx_rate_pct": 100.0, "uptime_seconds": 0, "latency_ms": 310.0}
            case "NETWORK_LATENCY":
                return {"p99_latency_ms": 24000.0, "packet_loss_pct": 15.0, "latency_ms": 280.0}
            case "DISK_FULL":
                return {"disk_used_pct": 98.5, "available_space_mb": 50.0}
            case _:
                return {"anomaly_score": 0.95, "error_rate_pct": 75.0}
