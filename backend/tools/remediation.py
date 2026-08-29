"""Permission-scoped remediation tools that only mutate the simulated institution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from ..digital_world.metrics import THRESHOLDS
from ..digital_world.models import AssetStatus, Incident
from ..governance.registry import AgentRegistry, AuditLog


TOOL_RISK = {
    "clear_cache": 8,
    "block_ip": 15,
    "tune_connection_pool": 18,
    "restart_service": 22,
    "scale_service": 25,
    "increase_resources": 28,
    "failover": 38,
    "rollback_deployment": 47,
    "quarantine_asset": 76,
    "delete_database": 100,
}


class RemediationExecutor:
    """Executes allow-listed tools against the digital twin, never the host OS."""

    def __init__(self, world: Any, registry: AgentRegistry, audit: AuditLog) -> None:
        self.world = world
        self.registry = registry
        self.audit = audit

    def execute(self, incident: Incident, plan: Dict[str, Any], *, simulate_failure: bool = False) -> Dict[str, Any]:
        self.registry.require("executor", "call_safe_tools")
        action = plan["actions"][0]
        tool = action["tool"]
        risk = TOOL_RISK.get(tool, 100)
        if tool not in TOOL_RISK or risk > 80:
            result = {"success": False, "tool": tool, "risk_score": risk, "error": "blocked_by_policy"}
            self.audit.append(
                "executor", "tool_blocked", incident_id=incident.incident_id,
                resource=tool, outcome="blocked", details=result,
            )
            return result

        if simulate_failure:
            result = {
                "success": False,
                "tool": tool,
                "risk_score": risk,
                "error": "simulated_first_attempt_failure",
                "changed_assets": [],
            }
            self.audit.append(
                "executor", "tool_execution", incident_id=incident.incident_id,
                resource=tool, outcome="failed", details=result,
            )
            return result

        failure_ids = self._related_failure_ids(incident)
        recovery_pct = float(action.get("recovery_pct", 0.96))
        recovered = [
            failure_id for failure_id in failure_ids
            if self.world.chaos_engine.recover_failure(failure_id, recovery_pct)
        ]

        changed_assets = []
        if not recovered:
            for asset_id in incident.affected_assets:
                asset = self.world.assets.get(asset_id)
                if asset:
                    self._normalize_asset(asset, recovery_pct)
                    changed_assets.append(asset_id)

        result = {
            "success": bool(recovered or changed_assets),
            "tool": tool,
            "risk_score": risk,
            "recovered_failures": recovered,
            "changed_assets": changed_assets or incident.affected_assets,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.audit.append(
            "executor", "tool_execution", incident_id=incident.incident_id,
            resource=tool, outcome="success" if result["success"] else "failed", details=result,
        )
        return result

    def _related_failure_ids(self, incident: Incident) -> List[str]:
        explicit = incident.metadata.get("failure_id")
        if explicit:
            failure = self.world.chaos_engine.active_failures.get(explicit)
            return [explicit] if failure and failure.get("active") else []
        affected = set(incident.affected_assets)
        matches = []
        for failure in self.world.chaos_engine.get_active_failures():
            failure_assets = set(failure.get("affected_assets", []))
            if failure.get("target_asset"):
                failure_assets.add(failure["target_asset"])
            if affected & failure_assets:
                matches.append(failure["failure_id"])
        return matches

    def _normalize_asset(self, asset: Any, recovery_pct: float) -> None:
        metrics = asset.metrics
        for metric_name, levels in THRESHOLDS.items():
            value = getattr(metrics, metric_name, None)
            if value is None or value < levels["warning"]:
                continue
            safe_target = levels["warning"] * 0.55
            new_value = value * (1 - recovery_pct) + safe_target * recovery_pct
            if metric_name in {"connection_count", "queue_depth"}:
                new_value = int(new_value)
            setattr(metrics, metric_name, max(0, new_value))
        asset.status = self.world.metrics_engine._derive_status(metrics)
        self.world.metrics_engine._record(asset.asset_id, metrics)

    def verify(self, incident: Incident, execution: Dict[str, Any]) -> Dict[str, Any]:
        assets = [self.world.assets[asset_id] for asset_id in incident.affected_assets if asset_id in self.world.assets]
        healthy = sum(1 for asset in assets if asset.status == AssetStatus.HEALTHY)
        critical = sum(1 for asset in assets if asset.status in (AssetStatus.CRITICAL, AssetStatus.OFFLINE))
        health_pct = round((healthy / len(assets) * 100) if assets else 100.0, 1)
        active_related = self._related_failure_ids(incident)
        success = execution.get("success", False) and critical == 0 and not active_related and health_pct >= 70
        return {
            "success": success,
            "healthy_assets": healthy,
            "checked_assets": len(assets),
            "critical_assets": critical,
            "health_pct": health_pct,
            "active_related_failures": active_related,
            "criteria": "no critical assets, no active related failure, >=70% affected assets healthy",
        }
