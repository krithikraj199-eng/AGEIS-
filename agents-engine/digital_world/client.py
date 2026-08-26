"""
Unified DigitalWorldClient for AEGIS Ω Intelligence Engine.
Encapsulates Member 1's real Digital World environment APIs and services:
1. Event stream
2. Metrics API
3. Dependency graph API
4. Historical incident API
5. Digital World action client
6. Chaos injection & test hooks
"""

from typing import Any, AsyncGenerator, Dict, List, Optional

from .models import (
    ActionResult,
    DigitalWorldEvent,
    HistoricalIncidentRecord,
    MetricReading,
)
from .metrics import MetricsAPI
from .dependency import DependencyGraphAPI
from .history import HistoryAPI
from .actions import ActionAPI
from .chaos import ChaosEngine


class DigitalWorldClient:
    """
    Unified client providing full access to Member 1's Digital World simulated infrastructure.
    """

    def __init__(self):
        self.metrics = MetricsAPI()
        self.dependency = DependencyGraphAPI()
        self.history = HistoryAPI()
        self.actions = ActionAPI()
        self.chaos = ChaosEngine(metrics_api=self.metrics)

    # -------------------------------------------------------------------------
    # 1. Event Stream API
    # -------------------------------------------------------------------------
    def generate_event(
        self,
        asset_id: str,
        event_type: str,
        severity: str = "INFO",
        metrics: Optional[Dict[str, Any]] = None,
        source: str = "digital_world_stream",
        correlation_id: Optional[str] = None,
    ) -> DigitalWorldEvent:
        """Create a new telemetry event."""
        return self.chaos.inject_fault(
            asset_id=asset_id,
            fault_type=event_type,
            severity=severity,
            metrics_override=metrics,
            correlation_id=correlation_id,
            source=source,
        )

    async def stream_events(
        self,
        events: List[DigitalWorldEvent],
        delay_sec: float = 0.05,
    ) -> AsyncGenerator[DigitalWorldEvent, None]:
        """Asynchronously stream a series of Digital World events."""
        import asyncio
        for ev in events:
            yield ev
            if delay_sec > 0:
                await asyncio.sleep(delay_sec)

    # -------------------------------------------------------------------------
    # 2. Metrics API
    # -------------------------------------------------------------------------
    def get_current_metric(self, asset_id: str, metric: str) -> float:
        """Query latest real-time metric reading for an asset."""
        return self.metrics.get_current_metric(asset_id, metric)

    def get_historical_metrics(
        self,
        asset_id: str,
        metric: str,
        window_minutes: int = 15,
    ) -> List[Dict[str, Any]]:
        """Query historical time series metrics for an asset."""
        return self.metrics.get_historical_metrics(asset_id, metric, window_minutes)

    def set_metric(self, asset_id: str, metric: str, value: float) -> None:
        """Set or update live metric value."""
        self.metrics.update_metric(asset_id, metric, value)

    # -------------------------------------------------------------------------
    # 3. Dependency Graph API
    # -------------------------------------------------------------------------
    def get_dependencies(self, asset_id: str, recursive: bool = True) -> List[str]:
        """Get upstream dependencies that this asset relies upon."""
        return self.dependency.get_dependencies(asset_id, recursive)

    def get_dependents(self, asset_id: str, recursive: bool = True) -> List[str]:
        """Get downstream dependents that rely upon this asset."""
        return self.dependency.get_dependents(asset_id, recursive)

    # -------------------------------------------------------------------------
    # 4. Historical Incident API
    # -------------------------------------------------------------------------
    def search_similar_incidents(
        self,
        signature: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Search historical incident database for matches against an incident signature."""
        return self.history.search_similar_incidents(signature, limit)

    def add_historical_incident(self, record: HistoricalIncidentRecord) -> None:
        """Record newly resolved incident into historical store."""
        self.history.add_incident(record)

    # -------------------------------------------------------------------------
    # 5. Action API (Whitelisted Tools)
    # -------------------------------------------------------------------------
    async def restart_service(
        self,
        asset_id: str,
        grace_period_sec: int = 15,
    ) -> Dict[str, Any]:
        """Restart target service gracefully."""
        res = await self.actions.restart_service(asset_id, grace_period_sec)
        # Normalize metric upon restart
        self.metrics.update_metric(asset_id, "latency_ms", 110.0)
        self.metrics.update_metric(asset_id, "query_latency_ms", 110.0)
        return res

    async def scale_service(
        self,
        asset_id: str,
        factor: float = 2.0,
        replicas: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Scale service capacity."""
        res = await self.actions.scale_service(asset_id, factor, replicas)
        # Normalize latency and connection metrics
        self.metrics.update_metric(asset_id, "latency_ms", 95.0)
        self.metrics.update_metric(asset_id, "query_latency_ms", 95.0)
        self.metrics.update_metric(asset_id, "connection_pool_usage_pct", 35.0)
        return res

    async def rollback_deployment(
        self,
        asset_id: str,
        target_version: str = "v1.14.0",
    ) -> Dict[str, Any]:
        """Rollback deployment to target version."""
        res = await self.actions.rollback_deployment(asset_id, target_version)
        self.metrics.update_metric(asset_id, "failed_auth_rate_pct", 0.5)
        self.metrics.update_metric(asset_id, "memory_used_pct", 45.0)
        return res

    async def clear_cache(
        self,
        asset_id: str,
        cache_pattern: str = "*",
    ) -> Dict[str, Any]:
        """Evict and invalidate cache."""
        res = await self.actions.clear_cache(asset_id, cache_pattern)
        self.metrics.update_metric(asset_id, "latency_ms", 75.0)
        return res

    async def quarantine_asset(
        self,
        asset_id: str,
        reason: str = "security_isolation",
    ) -> Dict[str, Any]:
        """Quarantine target asset."""
        return await self.actions.quarantine_asset(asset_id, reason)

    async def restore_configuration(
        self,
        asset_id: str,
        config_snapshot_id: str = "SNAP-GOLDEN-01",
    ) -> Dict[str, Any]:
        """Restore configuration from snapshot."""
        res = await self.actions.restore_configuration(asset_id, config_snapshot_id)
        self.metrics.update_metric(asset_id, "error_rate_pct", 0.0)
        return res

    # -------------------------------------------------------------------------
    # 6. Chaos Injection / Test Hooks
    # -------------------------------------------------------------------------
    def inject_fault(
        self,
        asset_id: str,
        fault_type: str,
        severity: str = "CRITICAL",
        metrics_override: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> DigitalWorldEvent:
        """Inject a fault into the Digital World environment."""
        return self.chaos.inject_fault(
            asset_id=asset_id,
            fault_type=fault_type,
            severity=severity,
            metrics_override=metrics_override,
            correlation_id=correlation_id,
        )

    def inject_cascading_failure(
        self,
        correlation_id: Optional[str] = None,
        root_asset_id: str = "DATABASE-01",
    ) -> List[DigitalWorldEvent]:
        """Inject a 4-tier cascading failure across the topology."""
        return self.chaos.inject_cascading_failure(
            correlation_id=correlation_id,
            root_asset_id=root_asset_id,
        )

    def reset(self) -> None:
        """Reset environment to healthy baseline state."""
        self.chaos.reset_environment()
        self.actions.action_history.clear()
        self.actions.asset_states.clear()


# Global singleton instance for runtime and agent access
_global_dw_client: Optional[DigitalWorldClient] = None


def get_digital_world_client() -> DigitalWorldClient:
    """Retrieve or initialize the global DigitalWorldClient singleton."""
    global _global_dw_client
    if _global_dw_client is None:
        _global_dw_client = DigitalWorldClient()
    return _global_dw_client
