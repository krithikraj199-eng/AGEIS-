"""
Unit Tests for Executor Agent and Scoped Remediation Tools in AEGIS Ω.
Tests risk gate enforcement (CRITICAL refused, HIGH held, LOW executed), tool schema validation,
refusal of invalid tools/parameters, and comprehensive audit trail logging.
"""

import asyncio
from typing import Any, Dict, List

from runtime.event_bus import EventBus
from tools.client import MockDigitalWorldClient
from tools.registry import ToolRegistry, ToolExecutionResult
from tools.restart_service import RestartServiceParams
from tools.scale_service import ScaleServiceParams
from tools.rollback_deployment import RollbackDeploymentParams
from tools.clear_cache import ClearCacheParams
from tools.quarantine_asset import QuarantineAssetParams
from tools.restore_configuration import RestoreConfigurationParams
from agents.executor.audit import AuditLogger, AuditRecord
from agents.executor.models import ExecutorOutput
from agents.executor.agent import ExecutorAgent, ExecutorInput


def test_critical_plan_is_refused():
    """Verify that a plan with CRITICAL risk (score >= 81 or BLOCKED gate) is refused execution."""
    async def _test():
        mock_client = MockDigitalWorldClient()
        registry = ToolRegistry(client=mock_client)
        audit_logger = AuditLogger()
        agent = ExecutorAgent(registry=registry, audit_logger=audit_logger)

        input_data = ExecutorInput(
            correlation_id="crit-corr-1",
            incident_id="INC-crit-1",
            plan_id="PLAN-CRIT-01",
            risk_score=92.0,
            tier="CRITICAL",
            gate_decision="BLOCKED",
            is_approved=False,
            actions_to_execute=[{"tool": "scale_service", "params": {"asset_id": "DATABASE-01", "factor": 2.0}}],
        )

        output: ExecutorOutput = await agent.process(input_data)

        # Execution must be refused
        assert output.execution_status == "REFUSED_CRITICAL_RISK"
        assert output.actuator_response_code == 403
        assert len(output.actions_executed) == 0
        assert len(mock_client.call_history) == 0  # Digital world never touched

        # Audit record must be generated
        assert len(output.audit_records) == 1
        assert output.audit_records[0].outcome == "REFUSED_CRITICAL_RISK"
        assert output.audit_records[0].risk_score == 92

    asyncio.run(_test())


def test_high_plan_requires_approval_and_is_held():
    """Verify that a plan with HIGH risk (score 61-80) is held for human approval."""
    async def _test():
        mock_client = MockDigitalWorldClient()
        registry = ToolRegistry(client=mock_client)
        audit_logger = AuditLogger()
        agent = ExecutorAgent(registry=registry, audit_logger=audit_logger)

        input_data = ExecutorInput(
            correlation_id="high-corr-1",
            incident_id="INC-high-1",
            plan_id="PLAN-HIGH-01",
            risk_score=75.0,
            tier="HIGH",
            gate_decision="HUMAN_APPROVAL_REQUIRED",
            requires_human_approval=True,
            is_approved=False,
            actions_to_execute=[{"tool": "quarantine_asset", "params": {"asset_id": "AUTH-01"}}],
        )

        output: ExecutorOutput = await agent.process(input_data)

        assert output.execution_status == "HELD_FOR_APPROVAL"
        assert output.actuator_response_code == 403
        assert len(output.actions_executed) == 0
        assert len(mock_client.call_history) == 0

        assert len(output.audit_records) == 1
        assert output.audit_records[0].outcome == "HELD_FOR_APPROVAL"

    asyncio.run(_test())


def test_low_plan_executes_successfully():
    """Verify that a plan with LOW risk (score <= 30) auto-executes."""
    async def _test():
        mock_client = MockDigitalWorldClient()
        registry = ToolRegistry(client=mock_client)
        audit_logger = AuditLogger()
        agent = ExecutorAgent(registry=registry, audit_logger=audit_logger)

        input_data = ExecutorInput(
            correlation_id="low-corr-1",
            incident_id="INC-low-1",
            plan_id="PLAN-LOW-01",
            risk_score=25.0,
            tier="LOW",
            gate_decision="AUTO_EXECUTE",
            is_approved=True,
            actions_to_execute=[
                {"tool": "scale_service", "params": {"asset_id": "DATABASE-01", "factor": 2.0, "replicas": 4}}
            ],
        )

        output: ExecutorOutput = await agent.process(input_data)

        assert output.execution_status == "SUCCESS"
        assert output.actuator_response_code == 200
        assert len(output.actions_executed) == 1
        assert len(mock_client.call_history) == 1
        assert mock_client.call_history[0]["action"] == "scale_service"
        assert mock_client.call_history[0]["asset_id"] == "DATABASE-01"

        assert len(output.audit_records) == 1
        assert output.audit_records[0].outcome == "SUCCESS"
        assert output.audit_records[0].tool_name == "scale_service"

    asyncio.run(_test())


def test_invalid_tool_is_refused():
    """Verify that an unauthorized / unknown tool is rejected with validation error."""
    async def _test():
        mock_client = MockDigitalWorldClient()
        registry = ToolRegistry(client=mock_client)
        agent = ExecutorAgent(registry=registry)

        input_data = ExecutorInput(
            correlation_id="bad-tool-1",
            incident_id="INC-bad-1",
            plan_id="PLAN-BAD-01",
            risk_score=20.0,
            tier="LOW",
            gate_decision="AUTO_EXECUTE",
            actions_to_execute=[
                {"tool": "nuke_datacenter", "params": {"asset_id": "DATABASE-01"}}
            ],
        )

        output: ExecutorOutput = await agent.process(input_data)

        assert output.execution_status == "FAILED_VALIDATION"
        assert output.actuator_response_code == 400
        assert len(mock_client.call_history) == 0

        assert len(output.audit_records) == 1
        assert output.audit_records[0].outcome == "FAILED_VALIDATION"
        assert "Disallowed or unknown tool" in output.audit_records[0].error_message

    asyncio.run(_test())


def test_invalid_parameters_are_refused():
    """Verify that malformed parameters (e.g. missing required fields or negative factors) are rejected."""
    async def _test():
        mock_client = MockDigitalWorldClient()
        registry = ToolRegistry(client=mock_client)
        agent = ExecutorAgent(registry=registry)

        # Missing required 'target_version' on rollback_deployment
        input_missing_param = ExecutorInput(
            correlation_id="param-bad-1",
            incident_id="INC-param-1",
            plan_id="PLAN-PARAM-01",
            risk_score=20.0,
            tier="LOW",
            gate_decision="AUTO_EXECUTE",
            actions_to_execute=[
                {"tool": "rollback_deployment", "params": {"asset_id": "API-01"}}  # missing target_version
            ],
        )

        output: ExecutorOutput = await agent.process(input_missing_param)

        assert output.execution_status == "FAILED_VALIDATION"
        assert output.actuator_response_code == 400
        assert len(mock_client.call_history) == 0
        assert "target_version" in str(output.audit_records[0].error_message)

    asyncio.run(_test())


def test_all_six_scoped_tools_execution():
    """Verify that all 6 scoped tools execute cleanly through ToolRegistry."""
    async def _test():
        mock_client = MockDigitalWorldClient()
        registry = ToolRegistry(client=mock_client)

        # 1. restart_service
        r1 = await registry.execute_tool("restart_service", {"asset_id": "DATABASE-01", "grace_period_sec": 10})
        assert r1.success is True

        # 2. scale_service
        r2 = await registry.execute_tool("scale_service", {"asset_id": "AUTH-01", "factor": 2.5})
        assert r2.success is True

        # 3. rollback_deployment
        r3 = await registry.execute_tool("rollback_deployment", {"asset_id": "API-01", "target_version": "v1.9.0"})
        assert r3.success is True

        # 4. clear_cache
        r4 = await registry.execute_tool("clear_cache", {"asset_id": "CACHE-01", "cache_pattern": "users:*"})
        assert r4.success is True

        # 5. quarantine_asset
        r5 = await registry.execute_tool("quarantine_asset", {"asset_id": "PORTAL-01", "reason": "ddos_mitigation"})
        assert r5.success is True

        # 6. restore_configuration
        r6 = await registry.execute_tool("restore_configuration", {"asset_id": "DATABASE-01", "config_snapshot_id": "snap-001"})
        assert r6.success is True

        assert len(mock_client.call_history) == 6

    asyncio.run(_test())


def test_audit_log_record_fields():
    """Verify that AuditRecord contains all required fields."""
    logger = AuditLogger()
    rec = logger.record_action(
        plan_id="PLAN-AUDIT-1",
        tool_name="restart_service",
        params={"asset_id": "DATABASE-01"},
        risk_score=22,
        outcome="SUCCESS",
    )

    data = rec.model_dump()
    assert "timestamp" in data
    assert data["plan_id"] == "PLAN-AUDIT-1"
    assert data["tool_name"] == "restart_service"
    assert data["params"] == {"asset_id": "DATABASE-01"}
    assert data["actor"] == "AEGIS_OMEGA_EXECUTOR"
    assert data["risk_score"] == 22
    assert data["outcome"] == "SUCCESS"


def test_executor_agent_event_bus_wiring():
    """Verify ExecutorAgent receives on incident.risk_approved and publishes to incident.executed."""
    async def _test():
        bus = EventBus()
        published_executions = []
        bus.subscribe("incident.executed", lambda ev: published_executions.append(ev))

        agent = ExecutorAgent(event_bus=bus)
        agent.start()

        risk_input = ExecutorInput(
            correlation_id="wiring-exec-1",
            incident_id="INC-wiring-exec-1",
            plan_id="PLAN-WIRING-01",
            risk_score=25.0,
            tier="LOW",
            gate_decision="AUTO_EXECUTE",
            is_approved=True,
            actions_to_execute=[{"tool": "scale_service", "params": {"asset_id": "DATABASE-01", "factor": 2.0}}],
        )

        await bus.publish("incident.risk_approved", risk_input)

        assert len(published_executions) == 1
        exec_out: ExecutorOutput = published_executions[0]
        assert exec_out.incident_id == "INC-wiring-exec-1"
        assert exec_out.execution_status == "SUCCESS"
        assert exec_out.actuator_response_code == 200
        assert len(exec_out.audit_records) == 1

        agent.stop()

    asyncio.run(_test())
