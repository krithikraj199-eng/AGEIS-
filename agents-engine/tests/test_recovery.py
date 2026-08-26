"""
Unit and Integration Tests for Recovery / Replanning Engine in AEGIS Ω.
Tests failure-tolerant autonomous recovery:
  Attempt 1: Force failure -> rollback -> replan -> exclude failed plan -> execute plan 2 -> verify success
Tests bounded 3-attempt retry limit, escalation on exhaustion, and attempt schema compliance.
"""

import asyncio
from typing import Any, Dict, List

from runtime.event_bus import EventBus
from tools.client import MockDigitalWorldClient
from tools.registry import ToolRegistry
from agents.planner.agent import PlannerAgent, PlannerInput
from agents.counterfactual.agent import CounterfactualAgent
from agents.risk.agent import RiskAgent
from agents.executor.agent import ExecutorAgent
from agents.verifier.agent import VerifierAgent
from agents.recovery.models import RecoveryAttempt, RecoveryOutput
from agents.recovery.agent import RecoveryAgent, RecoveryInput


def test_recovery_attempt_schema_structure():
    """Verify RecoveryAttempt schema contains attempt_number, plan_id, outcome, timestamp."""
    attempt = RecoveryAttempt(
        attempt_number=1,
        plan_id="PLAN-FAIL-01",
        outcome="FAILED",
        timestamp="2026-08-25T15:00:00Z",
        rollback_executed=True,
        rollback_details="Restarted DATABASE-01",
        error_message="Latency stayed at 820ms",
    )

    data = attempt.model_dump()
    assert data["attempt_number"] == 1
    assert data["plan_id"] == "PLAN-FAIL-01"
    assert data["outcome"] == "FAILED"
    assert "timestamp" in data
    assert data["rollback_executed"] is True


def test_immediate_success_on_attempt_one():
    """Verify that a successful verification on attempt 1 resolves the incident immediately."""
    async def _test():
        mock_client = MockDigitalWorldClient()
        registry = ToolRegistry(client=mock_client)
        agent = RecoveryAgent(registry=registry)

        rec_input = RecoveryInput(
            correlation_id="corr-rec-1",
            incident_id="INC-REC-1",
            plan_id="PLAN-SCALE-01",
            verification_passed=True,
            status="SUCCESS",
            metric="latency_ms",
            before=850.0,
            after=120.0,
        )

        output: RecoveryOutput = await agent.process(rec_input)

        assert output.final_status == "RESOLVED"
        assert output.rollback_required is False
        assert output.total_attempts == 1
        assert len(output.attempts) == 1
        assert output.attempts[0].outcome == "SUCCESS"
        assert output.attempts[0].attempt_number == 1

    asyncio.run(_test())


def test_failure_tolerant_autonomous_recovery_workflow():
    """
    Critical Integration Test:
    Attempt 1: Plan 1 fails verification.
    System executes rollback -> reinvokes Planner excluding Plan 1 ->
    Executes Plan 2 -> Verifier confirms SUCCESS -> Incident RESOLVED.
    """
    async def _test():
        bus = EventBus()
        mock_client = MockDigitalWorldClient()
        registry = ToolRegistry(client=mock_client)

        planner = PlannerAgent(event_bus=bus)
        counterfactual = CounterfactualAgent(event_bus=bus)
        risk = RiskAgent(event_bus=bus)
        executor = ExecutorAgent(event_bus=bus, registry=registry)
        verifier = VerifierAgent(event_bus=bus)
        recovery = RecoveryAgent(event_bus=bus, registry=registry)

        planner.start()
        counterfactual.start()
        risk.start()
        executor.start()
        verifier.start()
        recovery.start()

        incident_id = "INC-RECOVERY-TOLERANCE-01"
        corr_id = "corr-rec-tol-01"

        # --- Step 1: Attempt 1 - Send failed verification to Recovery ---
        failed_input = RecoveryInput(
            correlation_id=corr_id,
            incident_id=incident_id,
            plan_id="PLAN-FAIL-ATTEMPT-1",
            verification_passed=False,
            status="FAILED",
            metric="latency_ms",
            before=850.0,
            after=830.0,
            evidence="Latency remained above 200ms threshold",
            target_asset="DATABASE-01",
            rollback_method="restart_service",
        )

        # Listen for replan trigger on incident.root_cause and resolution on incident.resolved
        replan_events = []
        resolved_events = []
        bus.subscribe("incident.root_cause", lambda ev: replan_events.append(ev))
        bus.subscribe("incident.resolved", lambda ev: resolved_events.append(ev))

        out1: RecoveryOutput = await recovery.process(failed_input)

        # Assert Attempt 1 resulted in rollback and replanning trigger
        assert out1.final_status == "ROLLED_BACK"
        assert out1.rollback_required is True
        assert out1.total_attempts == 1
        assert out1.attempts[0].outcome == "FAILED"
        assert out1.attempts[0].rollback_executed is True

        # Assert rollback actually executed on mock client
        assert len(mock_client.call_history) >= 1
        assert mock_client.call_history[0]["action"] == "restart_service"

        # Assert replanning event was published with excluded plan
        assert len(replan_events) == 1
        assert "PLAN-FAIL-ATTEMPT-1" in replan_events[0]["excluded_plan_ids"]

        # Assert Attempt 2 executed autonomously through the pipeline to RESOLVED
        assert len(resolved_events) == 1
        final_out: RecoveryOutput = resolved_events[0]
        assert final_out.final_status == "RESOLVED"
        assert final_out.total_attempts == 2
        assert len(final_out.attempts) == 2
        assert final_out.attempts[0].attempt_number == 1
        assert final_out.attempts[0].outcome == "FAILED"
        assert final_out.attempts[0].rollback_executed is True
        assert final_out.attempts[1].attempt_number == 2
        assert final_out.attempts[1].outcome == "SUCCESS"

        planner.stop()
        counterfactual.stop()
        risk.stop()
        executor.stop()
        verifier.stop()
        recovery.stop()

    asyncio.run(_test())


def test_max_three_attempts_triggers_escalation():
    """Verify that after 3 consecutive failed attempts, the system escalates and halts."""
    async def _test():
        bus = EventBus()
        mock_client = MockDigitalWorldClient()
        registry = ToolRegistry(client=mock_client)
        agent = RecoveryAgent(event_bus=bus, registry=registry)
        agent.start()

        escalated_events = []
        bus.subscribe("incident.escalated", lambda ev: escalated_events.append(ev))

        incident_id = "INC-ESCALATION-01"
        corr_id = "corr-esc-01"

        # Attempt 1 Fail
        out1 = await agent.process(RecoveryInput(
            correlation_id=corr_id,
            incident_id=incident_id,
            plan_id="PLAN-TRY-1",
            verification_passed=False,
            status="FAILED",
            evidence="Fail 1",
        ))
        assert out1.final_status == "ROLLED_BACK"
        assert out1.total_attempts == 1

        # Attempt 2 Fail
        out2 = await agent.process(RecoveryInput(
            correlation_id=corr_id,
            incident_id=incident_id,
            plan_id="PLAN-TRY-2",
            verification_passed=False,
            status="FAILED",
            evidence="Fail 2",
        ))
        assert out2.final_status == "ROLLED_BACK"
        assert out2.total_attempts == 2

        # Attempt 3 Fail -> Max attempts reached!
        out3 = await agent.process(RecoveryInput(
            correlation_id=corr_id,
            incident_id=incident_id,
            plan_id="PLAN-TRY-3",
            verification_passed=False,
            status="FAILED",
            evidence="Fail 3",
        ))
        assert out3.final_status == "ESCALATION_REQUIRED"
        assert out3.total_attempts == 3
        assert len(out3.attempts) == 3
        assert "ESCALATION_REQUIRED" in out3.resolution_summary

        # Assert escalation event was published
        assert len(escalated_events) == 1
        assert escalated_events[0].final_status == "ESCALATION_REQUIRED"

        agent.stop()

    asyncio.run(_test())
