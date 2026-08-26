"""
Unit and Security Enforcement Tests for AEGIS Ω Governance Layer.
Tests:
  - Agent Registry (registration, heartbeat, get_agent, list_agents)
  - Agent Identity (scoped permissions, role boundaries)
  - Agent Gateway (sender authentication, schema validation, rate-limiting, message dispatch)
  - CRITICAL: Permission Revocation (remove Executor's tool:execute permission -> Gateway MUST reject execution)
  - Non-Executor Tool Execution Refusal (Investigator/Verifier blocked from calling tools)
"""

import asyncio
from typing import Any, Dict

from runtime.event_bus import EventBus
from tools.client import MockDigitalWorldClient
from tools.registry import ToolRegistry, ToolExecutionResult
from governance.identity import AgentPermission, DEFAULT_AGENT_PERMISSIONS, AgentIdentity
from governance.registry import AgentRecord, AgentRegistry
from governance.gateway import (
    AgentGateway,
    SlidingWindowRateLimiter,
    GovernanceSecurityError,
    PermissionDeniedError,
    RateLimitExceededError,
)
from agents.executor.agent import ExecutorAgent, ExecutorInput, ExecutorOutput


def test_agent_registry_lifecycle():
    """Verify registration, heartbeat, get, list, and permission mutations."""
    registry = AgentRegistry(auto_seed=False)

    # 1. Register agent
    rec = registry.register(
        agent_id="custom_worker_01",
        version="2.1.0",
        owner="SRE_TEAM",
        capabilities=["log_parsing"],
        permissions=["metrics:read", "incident:read"],
        status="ONLINE",
    )
    assert rec.agent_id == "custom_worker_01"
    assert rec.version == "2.1.0"
    assert "metrics:read" in rec.permissions

    # 2. Get agent
    fetched = registry.get_agent("custom_worker_01")
    assert fetched is not None
    assert fetched.agent_id == "custom_worker_01"

    # 3. Heartbeat
    old_hb = fetched.last_heartbeat
    success = registry.heartbeat("custom_worker_01")
    assert success is True
    assert registry.get_agent("custom_worker_01").last_heartbeat >= old_hb

    # 4. List agents
    agents = registry.list_agents()
    assert len(agents) == 1

    # 5. Revoke & grant permission
    assert registry.revoke_permission("custom_worker_01", "metrics:read") is True
    assert "metrics:read" not in registry.get_agent("custom_worker_01").permissions

    assert registry.grant_permission("custom_worker_01", "metrics:read") is True
    assert "metrics:read" in registry.get_agent("custom_worker_01").permissions


def test_default_agent_scoped_permissions():
    """Verify that default agent roles have strict least-privilege permissions."""
    registry = AgentRegistry(auto_seed=True)

    executor = registry.get_agent("executor")
    assert executor is not None
    assert AgentPermission.TOOL_EXECUTE in executor.permissions

    investigator = registry.get_agent("investigator")
    assert investigator is not None
    assert AgentPermission.METRICS_READ in investigator.permissions
    assert AgentPermission.TOOL_EXECUTE not in investigator.permissions  # Read-only

    verifier = registry.get_agent("verifier")
    assert verifier is not None
    assert AgentPermission.METRICS_READ in verifier.permissions
    assert AgentPermission.TOOL_EXECUTE not in verifier.permissions  # Read-only


def test_agent_gateway_send_and_authentication():
    """Verify Gateway sends valid messages and rejects unauthenticated senders."""
    async def _test():
        bus = EventBus()
        registry = AgentRegistry(auto_seed=True)
        gateway = AgentGateway(event_bus=bus, registry=registry)

        received = []
        bus.subscribe("incident.triage", lambda ev: received.append(ev))

        # 1. Valid registered sender
        success = await gateway.send(
            sender_id="sentinel",
            destination_topic="incident.triage",
            message={"incident_id": "INC-01", "status": "ANOMALY"},
        )
        assert success is True
        assert len(received) == 1

        # 2. Unregistered sender -> Raises GovernanceSecurityError
        caught_unreg = False
        try:
            await gateway.send(
                sender_id="rogue_agent_99",
                destination_topic="incident.triage",
                message={"data": "exploit"},
            )
        except GovernanceSecurityError as exc:
            caught_unreg = True
            assert "Unknown agent" in str(exc)
        assert caught_unreg is True

        # 3. Sender lacking required permission -> Raises PermissionDeniedError
        caught_perm = False
        try:
            await gateway.send(
                sender_id="verifier",
                destination_topic="infrastructure.control",
                message={"action": "restart"},
                required_permission=AgentPermission.TOOL_EXECUTE,
            )
        except PermissionDeniedError as exc:
            caught_perm = True
            assert "lacks required permission" in str(exc)
        assert caught_perm is True

    asyncio.run(_test())


def test_agent_gateway_rate_limiting():
    """Verify that exceeding rate limits is rejected by Gateway."""
    async def _test():
        bus = EventBus()
        registry = AgentRegistry(auto_seed=True)
        rate_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10.0)
        gateway = AgentGateway(event_bus=bus, registry=registry, rate_limiter=rate_limiter)

        # Send 5 allowed messages
        for i in range(5):
            await gateway.send("sentinel", "telemetry.processed", {"count": i})

        # 6th message exceeds limit -> Raises RateLimitExceededError
        caught_rate = False
        try:
            await gateway.send("sentinel", "telemetry.processed", {"count": 6})
        except RateLimitExceededError as exc:
            caught_rate = True
            assert "Rate limit exceeded" in str(exc)
        assert caught_rate is True

    asyncio.run(_test())


def test_remove_executor_permission_blocks_tool_execution():
    """
    CRITICAL TEST REQUIRED BY SPEC:
    1. Remove Executor's tool-call ('tool:execute') permission.
    2. Attempt tool execution via Executor / Gateway.
    3. Gateway MUST reject the request (real code enforcement).
    """
    async def _test():
        mock_client = MockDigitalWorldClient()
        tool_registry = ToolRegistry(client=mock_client)
        agent_registry = AgentRegistry(auto_seed=True)
        gateway = AgentGateway(registry=agent_registry, tool_registry=tool_registry)

        # Confirm Executor initially has tool:execute permission
        assert agent_registry.get_agent("executor") is not None
        assert AgentPermission.TOOL_EXECUTE in agent_registry.get_agent("executor").permissions

        # STEP 1: Explicitly revoke 'tool:execute' permission from Executor
        agent_registry.revoke_permission("executor", AgentPermission.TOOL_EXECUTE)
        assert AgentPermission.TOOL_EXECUTE not in agent_registry.get_agent("executor").permissions

        # STEP 2: Attempt tool execution through Gateway directly
        res: ToolExecutionResult = await gateway.execute_tool(
            agent_id="executor",
            tool_name="scale_service",
            params={"asset_id": "DATABASE-01", "factor": 2.0},
        )

        # STEP 3: Gateway MUST reject the request
        assert res.success is False
        assert "Permission Denied" in res.error_message
        assert len(mock_client.call_history) == 0  # Infrastructure was never touched

        # STEP 4: Attempt tool execution through ExecutorAgent wired to Gateway
        executor_agent = ExecutorAgent(registry=tool_registry, gateway=gateway)
        exec_input = ExecutorInput(
            correlation_id="corr-perm-test",
            incident_id="INC-PERM-01",
            plan_id="PLAN-PERM-01",
            risk_score=25.0,
            tier="LOW",
            gate_decision="AUTO_EXECUTE",
            actions_to_execute=[{"tool": "scale_service", "params": {"asset_id": "DATABASE-01", "factor": 2.0}}],
        )

        out: ExecutorOutput = await executor_agent.process(exec_input)

        # Executor must fail validation / permission check
        assert out.execution_status == "FAILED_VALIDATION"
        assert out.actuator_response_code == 400
        assert len(out.actions_executed) == 0
        assert len(mock_client.call_history) == 0
        assert "Permission Denied" in out.audit_records[0].error_message

    asyncio.run(_test())


def test_non_executor_agent_cannot_execute_tools():
    """Verify that unauthorized agents (e.g. investigator, verifier) cannot execute tools."""
    async def _test():
        mock_client = MockDigitalWorldClient()
        tool_registry = ToolRegistry(client=mock_client)
        agent_registry = AgentRegistry(auto_seed=True)
        gateway = AgentGateway(registry=agent_registry, tool_registry=tool_registry)

        # Investigator tries to execute restart_service
        res_inv = await gateway.execute_tool(
            agent_id="investigator",
            tool_name="restart_service",
            params={"asset_id": "AUTH-01"},
        )
        assert res_inv.success is False
        assert "Permission Denied" in res_inv.error_message
        assert len(mock_client.call_history) == 0

        # Verifier tries to execute clear_cache
        res_ver = await gateway.execute_tool(
            agent_id="verifier",
            tool_name="clear_cache",
            params={"asset_id": "CACHE-01"},
        )
        assert res_ver.success is False
        assert "Permission Denied" in res_ver.error_message
        assert len(mock_client.call_history) == 0

    asyncio.run(_test())
