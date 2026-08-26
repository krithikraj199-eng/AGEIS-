"""
Agent Registry for AEGIS Ω Governance Layer.
Tracks agent registration, capabilities, permissions, status, and liveness heartbeats.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from .identity import DEFAULT_AGENT_PERMISSIONS, AgentPermission

logger = logging.getLogger(__name__)


class AgentRecord(BaseModel):
    """
    Required schema for registered agent record:
    { agent_id, version, owner, capabilities, permissions, status, last_heartbeat }
    """
    agent_id: str
    version: str = "1.0.0"
    owner: str = "AEGIS_OMEGA_SYSTEM"
    capabilities: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    status: str = "ONLINE"  # ONLINE, OFFLINE, SUSPENDED
    last_heartbeat: str


class AgentRegistry:
    """
    Central Agent Registry managing authentication, liveness, and dynamic permissions.
    """

    def __init__(self, auto_seed: bool = True):
        self._registry: Dict[str, AgentRecord] = {}
        if auto_seed:
            self._seed_default_agents()

    def _seed_default_agents(self) -> None:
        """Register default 12 AEGIS Ω agents."""
        now_ts = datetime.now(timezone.utc).isoformat()
        for role_name, perms in DEFAULT_AGENT_PERMISSIONS.items():
            agent_id = role_name.lower().replace(" ", "_")
            self._registry[agent_id] = AgentRecord(
                agent_id=agent_id,
                version="1.0.0",
                owner="AEGIS_OMEGA_SYSTEM",
                capabilities=[f"role:{agent_id}"],
                permissions=list(perms),
                status="ONLINE",
                last_heartbeat=now_ts,
            )

    def register(
        self,
        agent_id: str,
        version: str = "1.0.0",
        owner: str = "AEGIS_OMEGA_SYSTEM",
        capabilities: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        status: str = "ONLINE",
    ) -> AgentRecord:
        """Register a new agent or update an existing registration."""
        now_ts = datetime.now(timezone.utc).isoformat()
        record = AgentRecord(
            agent_id=agent_id,
            version=version,
            owner=owner,
            capabilities=capabilities or [],
            permissions=permissions or [],
            status=status,
            last_heartbeat=now_ts,
        )
        self._registry[agent_id] = record
        logger.info(f"Agent '{agent_id}' registered successfully (Status: {status}).")
        return record

    def heartbeat(self, agent_id: str) -> bool:
        """Update last heartbeat timestamp for agent."""
        if agent_id in self._registry:
            self._registry[agent_id].last_heartbeat = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        """Retrieve agent registration record by ID."""
        return self._registry.get(agent_id)

    def list_agents(self) -> List[AgentRecord]:
        """List all currently registered agents."""
        return list(self._registry.values())

    def update_permissions(self, agent_id: str, permissions: List[str]) -> bool:
        """Update the complete permission list for an agent."""
        if agent_id in self._registry:
            self._registry[agent_id].permissions = list(permissions)
            logger.info(f"Updated permissions for agent '{agent_id}': {permissions}")
            return True
        return False

    def grant_permission(self, agent_id: str, permission: str) -> bool:
        """Grant a specific permission to an agent."""
        if agent_id in self._registry:
            if permission not in self._registry[agent_id].permissions:
                self._registry[agent_id].permissions.append(permission)
            return True
        return False

    def revoke_permission(self, agent_id: str, permission: str) -> bool:
        """Revoke a specific permission from an agent."""
        if agent_id in self._registry:
            if permission in self._registry[agent_id].permissions:
                self._registry[agent_id].permissions.remove(permission)
                logger.warning(f"Revoked permission '{permission}' from agent '{agent_id}'.")
            return True
        return False
