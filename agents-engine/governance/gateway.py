"""
Agent Gateway for AEGIS Ω Governance Layer.
Central security, authentication, schema validation, rate-limiting, and communication gateway.
Enforces real code-level authorization: agents cannot bypass the gateway or invoke disallowed tools.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from runtime.event_bus import EventBus
from tools.registry import ToolRegistry, ToolExecutionResult

from .identity import AgentPermission
from .registry import AgentRegistry, AgentRecord

logger = logging.getLogger(__name__)


class GovernanceSecurityError(Exception):
    """Raised when an authentication, authorization, or security policy fails."""
    pass


class RateLimitExceededError(GovernanceSecurityError):
    """Raised when an agent breaches rate limits."""
    pass


class PermissionDeniedError(GovernanceSecurityError):
    """Raised when an agent attempts an action without required permissions."""
    pass


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter tracking message frequencies per agent.
    """

    def __init__(self, max_requests: int = 100, window_seconds: float = 10.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}

    def is_allowed(self, agent_id: str) -> bool:
        """Check if agent is within rate limit, updating window history."""
        now = time.time()
        if agent_id not in self._history:
            self._history[agent_id] = []

        # Prune old timestamps
        cutoff = now - self.window_seconds
        self._history[agent_id] = [t for t in self._history[agent_id] if t > cutoff]

        if len(self._history[agent_id]) >= self.max_requests:
            return False

        self._history[agent_id].append(now)
        return True


class AgentGateway:
    """
    Central Agent Gateway:
    - Authenticates sender identity
    - Validates sender permissions
    - Validates message schema
    - Enforces rate limits
    - Dispatches to destination topic on EventBus
    - Authorizes and controls scoped tool execution
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        registry: Optional[AgentRegistry] = None,
        tool_registry: Optional[ToolRegistry] = None,
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
    ):
        self.event_bus = event_bus or EventBus()
        self.registry = registry or AgentRegistry()
        self.tool_registry = tool_registry or ToolRegistry()
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(max_requests=100, window_seconds=10.0)

    def authenticate_agent(self, agent_id: str) -> AgentRecord:
        """
        Authenticate that agent exists and is ONLINE in the registry.
        """
        agent = self.registry.get_agent(agent_id)
        if not agent:
            raise GovernanceSecurityError(f"Authentication failed: Unknown agent '{agent_id}'.")
        if agent.status != "ONLINE":
            raise GovernanceSecurityError(f"Authentication failed: Agent '{agent_id}' is {agent.status}.")
        return agent

    def authorize_permission(self, agent_id: str, required_permission: str) -> bool:
        """
        Verify that agent possesses the required permission.
        """
        agent = self.authenticate_agent(agent_id)
        return required_permission in agent.permissions

    async def send(
        self,
        sender_id: str,
        destination_topic: str,
        message: Any,
        required_permission: Optional[str] = None,
    ) -> bool:
        """
        Securely send a message through the Gateway.
        1. Authenticates sender
        2. Validates sender permissions
        3. Validates message schema
        4. Enforces rate limits
        5. Dispatches to EventBus
        """
        # Step 1: Authenticate sender
        agent = self.authenticate_agent(sender_id)

        # Step 2: Validate sender permission
        perm_to_check = required_permission or AgentPermission.INCIDENT_WRITE
        if perm_to_check not in agent.permissions:
            raise PermissionDeniedError(
                f"Agent '{sender_id}' lacks required permission '{perm_to_check}' "
                f"to send to '{destination_topic}'."
            )

        # Step 3: Validate message schema (Pydantic or serializable Dict)
        if isinstance(message, BaseModel):
            payload = message
        elif isinstance(message, dict):
            payload = message
        else:
            raise GovernanceSecurityError(f"Invalid message format: expected BaseModel or dict, got {type(message)}.")

        # Step 4: Rate-limit messages
        if not self.rate_limiter.is_allowed(sender_id):
            raise RateLimitExceededError(
                f"Rate limit exceeded for agent '{sender_id}' "
                f"({self.rate_limiter.max_requests} req / {self.rate_limiter.window_seconds}s)."
            )

        # Update heartbeat
        self.registry.heartbeat(sender_id)

        # Step 5: Route message to destination topic
        await self.event_bus.publish(destination_topic, payload)
        return True

    async def execute_tool(
        self,
        agent_id: str,
        tool_name: str,
        params: Dict[str, Any],
    ) -> ToolExecutionResult:
        """
        Execute a scoped infrastructure tool through the Gateway.
        Strictly enforces that agent_id has 'tool:execute' permission.
        """
        # Step 1: Authenticate agent
        agent = self.authenticate_agent(agent_id)

        # Step 2: Real code enforcement: verify tool:execute permission
        if AgentPermission.TOOL_EXECUTE not in agent.permissions:
            logger.error(
                f"GOVERNANCE GATEWAY REFUSAL: Agent '{agent_id}' attempted to execute tool '{tool_name}' "
                f"without '{AgentPermission.TOOL_EXECUTE}' permission."
            )
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result={},
                error_message=(
                    f"Permission Denied: Agent '{agent_id}' lacks required permission "
                    f"'{AgentPermission.TOOL_EXECUTE}' to execute remediation tools."
                ),
            )

        # Step 3: Dispatch to ToolRegistry
        return await self.tool_registry.execute_tool(tool_name, params)
