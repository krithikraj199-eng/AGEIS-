"""
Action API for Digital World Environment.
Provides actuations across the 6 whitelisted infrastructure operational tools.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from .models import ActionResult

logger = logging.getLogger(__name__)


class ActionAPI:
    """
    Member 1's Digital World Action API interface:
    - restart_service()
    - scale_service()
    - rollback_deployment()
    - clear_cache()
    - quarantine_asset()
    - restore_configuration()
    """

    def __init__(self):
        self.action_history: List[Dict[str, Any]] = []
        self.asset_states: Dict[str, Dict[str, Any]] = {}

    async def restart_service(
        self,
        asset_id: str,
        grace_period_sec: int = 15,
    ) -> Dict[str, Any]:
        """Restart target service gracefully."""
        res = ActionResult(
            action="restart_service",
            asset_id=asset_id,
            status="SUCCESS",
            message=f"Successfully restarted {asset_id} with {grace_period_sec}s grace period.",
            details={"grace_period_sec": grace_period_sec, "restarted_at": datetime.now(timezone.utc).isoformat()},
        )
        self.action_history.append(res.model_dump())
        self.asset_states[asset_id] = {"status": "HEALTHY", "restarted": True}
        return res.model_dump()

    async def scale_service(
        self,
        asset_id: str,
        factor: float = 2.0,
        replicas: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Scale service capacity horizontally or vertically."""
        target_replicas = replicas or int(round(2 * factor))
        res = ActionResult(
            action="scale_service",
            asset_id=asset_id,
            status="SUCCESS",
            message=f"Scaled {asset_id} by factor {factor} (target replicas: {target_replicas}).",
            details={"factor": factor, "replicas": target_replicas, "scaled_at": datetime.now(timezone.utc).isoformat()},
        )
        self.action_history.append(res.model_dump())
        self.asset_states[asset_id] = {"status": "SCALED", "factor": factor, "replicas": target_replicas}
        return res.model_dump()

    async def rollback_deployment(
        self,
        asset_id: str,
        target_version: str = "v1.14.0",
    ) -> Dict[str, Any]:
        """Rollback service to a previously verified release artifact."""
        res = ActionResult(
            action="rollback_deployment",
            asset_id=asset_id,
            status="SUCCESS",
            message=f"Rolled back {asset_id} to target version {target_version}.",
            details={"target_version": target_version, "rolled_back_at": datetime.now(timezone.utc).isoformat()},
        )
        self.action_history.append(res.model_dump())
        self.asset_states[asset_id] = {"status": "ROLLED_BACK", "version": target_version}
        return res.model_dump()

    async def clear_cache(
        self,
        asset_id: str,
        cache_pattern: str = "*",
    ) -> Dict[str, Any]:
        """Evict and invalidate cache entries."""
        res = ActionResult(
            action="clear_cache",
            asset_id=asset_id,
            status="SUCCESS",
            message=f"Cleared cache keys on {asset_id} matching pattern '{cache_pattern}'.",
            details={"cache_pattern": cache_pattern, "cleared_at": datetime.now(timezone.utc).isoformat()},
        )
        self.action_history.append(res.model_dump())
        self.asset_states[asset_id] = {"status": "CACHE_CLEARED", "pattern": cache_pattern}
        return res.model_dump()

    async def quarantine_asset(
        self,
        asset_id: str,
        reason: str = "security_isolation",
    ) -> Dict[str, Any]:
        """Isolate asset from network routing mesh."""
        res = ActionResult(
            action="quarantine_asset",
            asset_id=asset_id,
            status="SUCCESS",
            message=f"Quarantined asset {asset_id} for reason: {reason}.",
            details={"reason": reason, "quarantined_at": datetime.now(timezone.utc).isoformat()},
        )
        self.action_history.append(res.model_dump())
        self.asset_states[asset_id] = {"status": "QUARANTINED", "reason": reason}
        return res.model_dump()

    async def restore_configuration(
        self,
        asset_id: str,
        config_snapshot_id: str = "SNAP-GOLDEN-01",
    ) -> Dict[str, Any]:
        """Restore asset configuration from a verified golden snapshot."""
        res = ActionResult(
            action="restore_configuration",
            asset_id=asset_id,
            status="SUCCESS",
            message=f"Restored configuration on {asset_id} from snapshot {config_snapshot_id}.",
            details={"snapshot_id": config_snapshot_id, "restored_at": datetime.now(timezone.utc).isoformat()},
        )
        self.action_history.append(res.model_dump())
        self.asset_states[asset_id] = {"status": "CONFIG_RESTORED", "snapshot_id": config_snapshot_id}
        return res.model_dump()
