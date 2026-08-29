"""Agent identity, capability authorization, and immutable audit records."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from ..digital_world.models import AgentRegistryEntry


AGENT_DEFINITIONS = (
    ("sentinel", "Sentinel", ("read_metrics", "read_events", "create_incident")),
    ("investigator", "Investigator", ("read_events", "read_metrics", "read_memory")),
    ("evidence", "Evidence Agent", ("read_events", "read_metrics")),
    ("dependency", "Dependency Agent", ("read_graph",)),
    ("security", "Security Agent", ("read_events", "classify_security")),
    ("root_cause", "Root Cause Engine", ("read_evidence", "read_memory")),
    ("planner", "Planner", ("create_plan", "read_memory")),
    ("counterfactual", "Counterfactual Engine", ("simulate_plan",)),
    ("risk", "Risk Engine", ("score_risk",)),
    ("executor", "Executor", ("call_safe_tools",)),
    ("verifier", "Verifier", ("read_metrics", "verify_action")),
    ("recovery", "Recovery Agent", ("rollback", "replan")),
    ("memory", "Memory Agent", ("read_memory", "write_memory")),
    ("predictor", "Prediction Engine", ("read_metrics", "create_prediction")),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentRegistry:
    """In-process capability registry used by the agent gateway and tools."""

    def __init__(self) -> None:
        self._agents: Dict[str, AgentRegistryEntry] = {}
        for agent_id, name, permissions in AGENT_DEFINITIONS:
            self._agents[agent_id] = AgentRegistryEntry(
                agent_id=agent_id,
                name=name,
                capabilities=list(permissions),
                permissions=list(permissions),
                last_heartbeat=utc_now(),
                metadata={"runtime": "local-deterministic", "model_optional": True},
            )

    def heartbeat_all(self) -> None:
        now = utc_now()
        for entry in self._agents.values():
            entry.last_heartbeat = now
            entry.health = "healthy"

    def authorize(self, agent_id: str, permission: str) -> bool:
        entry = self._agents.get(agent_id)
        return bool(entry and entry.status == "active" and permission in entry.permissions)

    def require(self, agent_id: str, permission: str) -> None:
        if not self.authorize(agent_id, permission):
            raise PermissionError(f"Agent {agent_id!r} lacks permission {permission!r}")

    def list(self) -> List[Dict[str, Any]]:
        self.heartbeat_all()
        return [entry.model_dump(mode="json") for entry in self._agents.values()]

    def summary(self) -> Dict[str, Any]:
        agents = self.list()
        return {
            "total": len(agents),
            "healthy": sum(1 for agent in agents if agent["health"] == "healthy"),
            "active": sum(1 for agent in agents if agent["status"] == "active"),
            "agents": agents,
        }


class AuditLog:
    """Bounded append-only audit stream for governance and demo inspection."""

    def __init__(self, max_entries: int = 5000) -> None:
        self._entries: deque[Dict[str, Any]] = deque(maxlen=max_entries)
        self._counter = 0

    def append(
        self,
        actor: str,
        action: str,
        *,
        incident_id: str | None = None,
        resource: str | None = None,
        outcome: str = "success",
        details: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        self._counter += 1
        entry = {
            "audit_id": f"AUD-{self._counter:06d}",
            "timestamp": utc_now().isoformat(),
            "actor": actor,
            "action": action,
            "incident_id": incident_id,
            "resource": resource,
            "outcome": outcome,
            "details": details or {},
        }
        self._entries.append(entry)
        return entry

    def recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(self._entries)[-max(1, min(limit, 500)) :][::-1]

