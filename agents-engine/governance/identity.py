"""
Agent Identity and Scoped Permissions for AEGIS Ω Governance Layer.
Defines role-based capabilities and fine-grained permissions for all agents.
"""

from typing import Dict, List, Set
from pydantic import BaseModel, Field


class AgentPermission:
    """Standardized granular permission string constants."""
    TOOL_EXECUTE = "tool:execute"
    METRICS_READ = "metrics:read"
    INCIDENT_READ = "incident:read"
    INCIDENT_WRITE = "incident:write"
    TOPOLOGY_READ = "topology:read"
    SECURITY_AUDIT = "security:audit"
    RECOVERY_MANAGE = "recovery:manage"
    HISTORY_READ = "history:read"
    SIMULATION_RUN = "simulation:run"
    GOVERNANCE_EVALUATE = "governance:evaluate"


# Pre-configured default permission matrix across all 12 agents
DEFAULT_AGENT_PERMISSIONS: Dict[str, List[str]] = {
    "Sentinel": [
        AgentPermission.METRICS_READ,
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
    ],
    "Investigator": [
        AgentPermission.METRICS_READ,
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
        AgentPermission.HISTORY_READ,
    ],
    "Evidence": [
        AgentPermission.METRICS_READ,
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
    ],
    "Dependency": [
        AgentPermission.TOPOLOGY_READ,
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
    ],
    "Security": [
        AgentPermission.SECURITY_AUDIT,
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
    ],
    "Root Cause": [
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
    ],
    "Planner": [
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
    ],
    "Counterfactual": [
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
        AgentPermission.SIMULATION_RUN,
    ],
    "Risk": [
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
        AgentPermission.GOVERNANCE_EVALUATE,
    ],
    "Executor": [
        AgentPermission.TOOL_EXECUTE,  # ONLY Executor (and delegated Recovery) can execute tools
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
    ],
    "Verifier": [
        AgentPermission.METRICS_READ,  # Read-only metric access
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
    ],
    "Recovery": [
        AgentPermission.RECOVERY_MANAGE,
        AgentPermission.INCIDENT_READ,
        AgentPermission.INCIDENT_WRITE,
        AgentPermission.TOOL_EXECUTE,  # For rollback execution
    ],
}


class AgentIdentity(BaseModel):
    """
    Authenticated identity representation for an agent in the governance mesh.
    """
    agent_id: str
    role_name: str
    owner: str = "AEGIS_OMEGA_SYSTEM"
    permissions: Set[str] = Field(default_factory=set)

    def has_permission(self, permission: str) -> bool:
        """Check if agent possesses the required permission."""
        return permission in self.permissions
