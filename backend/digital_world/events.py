"""
AEGIS Ω — Event Engine

Generates a continuous stream of events from the digital world.
Events are produced by natural metric fluctuations, threshold
breaches, configuration changes, and injected failures.
"""

from __future__ import annotations

import random
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Callable, Dict, Deque, List, Optional

from .models import (
    Asset, AssetStatus, AssetType, Event, EventType, Severity
)
from .metrics import MetricsEngine


# Map metric alerts → EventType
_METRIC_EVENT_MAP = {
    ("cpu_percent", "warning"): EventType.CPU_WARNING,
    ("cpu_percent", "critical"): EventType.CPU_CRITICAL,
    ("memory_percent", "warning"): EventType.MEMORY_WARNING,
    ("memory_percent", "critical"): EventType.MEMORY_CRITICAL,
    ("disk_percent", "warning"): EventType.DISK_WARNING,
    ("disk_percent", "critical"): EventType.DISK_FULL,
    ("network_latency_ms", "warning"): EventType.NETWORK_LATENCY,
    ("network_latency_ms", "critical"): EventType.NETWORK_FAILURE,
    ("error_rate", "warning"): EventType.APPLICATION_ERROR,
    ("error_rate", "critical"): EventType.APPLICATION_CRASH,
    ("response_time_ms", "warning"): EventType.DATABASE_TIMEOUT,
    ("response_time_ms", "critical"): EventType.DATABASE_TIMEOUT,
    ("connection_count", "warning"): EventType.DATABASE_OVERLOAD,
    ("connection_count", "critical"): EventType.DATABASE_OVERLOAD,
}

_SEVERITY_MAP = {
    "warning": Severity.MEDIUM,
    "critical": Severity.CRITICAL,
}


class EventEngine:
    """
    Produces events from the digital world.  Three sources:

    1. Metric threshold breaches (from MetricsEngine)
    2. Random operational events (logins, backups, deployments)
    3. Injected chaos events
    """

    def __init__(self, metrics_engine: MetricsEngine):
        self.metrics_engine = metrics_engine
        self.event_stream: Deque[Event] = deque(maxlen=5000)
        self.subscribers: List[Callable[[Event], None]] = []
        self.correlation_counter = 0
        self.event_count = 0

    # ──────────────────────────────────────────────────────
    # SUBSCRIPTIONS (for the Sentinel and Dashboard)
    # ──────────────────────────────────────────────────────

    def subscribe(self, callback: Callable[[Event], None]):
        self.subscribers.append(callback)

    def _publish(self, event: Event):
        self.event_stream.append(event)
        self.event_count += 1
        for cb in self.subscribers:
            try:
                cb(event)
            except Exception:
                pass

    # ──────────────────────────────────────────────────────
    # GENERATE EVENTS FROM METRICS
    # ──────────────────────────────────────────────────────

    def generate_metric_events(self, assets: Dict[str, Asset],
                                sim_hour: int = 12) -> List[Event]:
        """
        Update all asset metrics and produce events from
        threshold breaches.
        """
        events: List[Event] = []

        for asset_id, asset in assets.items():
            # Natural metric drift
            self.metrics_engine.update_metrics_naturally(asset, sim_hour)

            # Check thresholds
            alerts = self.metrics_engine.check_thresholds(asset)
            for alert in alerts:
                key = (alert["metric"], alert["severity"])
                event_type = _METRIC_EVENT_MAP.get(key)
                severity = _SEVERITY_MAP.get(alert["severity"], Severity.LOW)

                if event_type:
                    event = Event(
                        asset_id=asset_id,
                        event_type=event_type,
                        severity=severity,
                        message=alert["message"],
                        metrics_snapshot=asset.metrics.model_copy(),
                        source="metrics_engine",
                    )
                    events.append(event)
                    self._publish(event)

        # Also generate some ambient operational events
        ambient = self._generate_ambient_events(assets, sim_hour)
        events.extend(ambient)

        return events

    # ──────────────────────────────────────────────────────
    # AMBIENT / BACKGROUND EVENTS
    # ──────────────────────────────────────────────────────

    def _generate_ambient_events(self, assets: Dict[str, Asset],
                                  sim_hour: int) -> List[Event]:
        """Generate low-noise background events."""
        events: List[Event] = []

        # Login events
        if random.random() < 0.3:
            app_ids = [a for a, asset in assets.items()
                       if asset.asset_type == AssetType.APPLICATION]
            if app_ids:
                target = random.choice(app_ids)
                is_failure = random.random() < 0.05
                event = Event(
                    asset_id=target,
                    event_type=EventType.LOGIN_FAILURE if is_failure else EventType.LOGIN_SUCCESS,
                    severity=Severity.LOW if not is_failure else Severity.MEDIUM,
                    message=f"{'Failed' if is_failure else 'Successful'} login attempt",
                    source="auth_system",
                )
                events.append(event)
                self._publish(event)

        # Backup events
        if random.random() < 0.05 and 2 <= sim_hour <= 5:
            is_failure = random.random() < 0.08
            event = Event(
                asset_id="BACKUP-01",
                event_type=EventType.BACKUP_FAILURE if is_failure else EventType.BACKUP_SUCCESS,
                severity=Severity.HIGH if is_failure else Severity.INFO,
                message=f"Nightly backup {'failed' if is_failure else 'completed'}",
                source="backup_system",
            )
            events.append(event)
            self._publish(event)

        return events

    # ──────────────────────────────────────────────────────
    # CHAOS / INJECTED EVENTS
    # ──────────────────────────────────────────────────────

    def create_event(self, asset_id: str, event_type: EventType,
                     severity: Severity, message: str,
                     correlation_id: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> Event:
        """Create and publish a custom event."""
        event = Event(
            asset_id=asset_id,
            event_type=event_type,
            severity=severity,
            message=message,
            correlation_id=correlation_id,
            source="chaos_engine",
            metadata=metadata or {},
        )
        self._publish(event)
        return event

    def new_correlation_id(self) -> str:
        self.correlation_counter += 1
        return f"CORR-{self.correlation_counter:06d}"

    # ──────────────────────────────────────────────────────
    # QUERIES
    # ──────────────────────────────────────────────────────

    def get_recent_events(self, count: int = 50) -> List[Event]:
        return list(self.event_stream)[-count:]

    def get_events_for_asset(self, asset_id: str, count: int = 50) -> List[Event]:
        return [e for e in self.event_stream if e.asset_id == asset_id][-count:]

    def get_events_by_severity(self, severity: Severity, count: int = 50) -> List[Event]:
        return [e for e in self.event_stream if e.severity == severity][-count:]

    def get_events_by_correlation(self, correlation_id: str) -> List[Event]:
        return [e for e in self.event_stream if e.correlation_id == correlation_id]

    def get_event_stats(self) -> Dict[str, Any]:
        recent = list(self.event_stream)[-200:]
        severity_counts = {}
        type_counts = {}
        for e in recent:
            severity_counts[e.severity.value] = severity_counts.get(e.severity.value, 0) + 1
            type_counts[e.event_type.value] = type_counts.get(e.event_type.value, 0) + 1

        return {
            "total_events": self.event_count,
            "stream_size": len(self.event_stream),
            "recent_severity": severity_counts,
            "recent_types": type_counts,
        }
