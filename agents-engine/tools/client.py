"""
DigitalWorldClient Protocol and Live Implementation for AEGIS Ω.
Connects directly to Member 1's Digital World infrastructure environment.
"""

from typing import Any, Dict, List, Optional, Protocol
from digital_world.client import DigitalWorldClient, get_digital_world_client


class DigitalWorldClientProtocol(Protocol):
    """
    Protocol representing Member 1's Digital World actuation API.
    All infrastructure modifications pass through this interface.
    """

    async def restart_service(self, asset_id: str, grace_period_sec: int = 15) -> Dict[str, Any]:
        """Restart target service gracefully."""
        ...

    async def scale_service(
        self,
        asset_id: str,
        factor: float = 2.0,
        replicas: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Scale service capacity horizontally or vertically."""
        ...

    async def rollback_deployment(self, asset_id: str, target_version: str) -> Dict[str, Any]:
        """Rollback service to a previously verified release artifact."""
        ...

    async def clear_cache(self, asset_id: str, cache_pattern: str = "*") -> Dict[str, Any]:
        """Evict and invalidate cache entries."""
        ...

    async def quarantine_asset(self, asset_id: str, reason: str = "security_isolation") -> Dict[str, Any]:
        """Isolate asset from network routing mesh."""
        ...

    async def restore_configuration(self, asset_id: str, config_snapshot_id: str) -> Dict[str, Any]:
        """Restore asset configuration from snapshot."""
        ...


class MockDigitalWorldClient(DigitalWorldClient):
    """
    Backwards-compatible alias for Member 1's DigitalWorldClient.
    Provides live Digital World actuation and state tracking.
    """

    @property
    def call_history(self) -> List[Dict[str, Any]]:
        """Backwards compatibility for tests inspecting action call history."""
        return self.actions.action_history

    @property
    def asset_states(self) -> Dict[str, Dict[str, Any]]:
        """Backwards compatibility for tests inspecting asset states."""
        return self.actions.asset_states
