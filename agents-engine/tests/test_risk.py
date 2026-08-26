"""
Unit Tests for Risk Engine in AEGIS Ω.
Tests 100% deterministic risk scoring, exact boundary thresholds (30, 31, 60, 61, 80, 81, 100),
security event penalty scaling, and execution gate enforcement.
"""

import asyncio
from typing import Any, Dict

from runtime.event_bus import EventBus
from agents.risk.models import GateDecision, RiskOutput, RiskTier
from agents.risk.calculator import DeterministicRiskCalculator
from agents.risk.agent import RiskAgent, RiskInput
from agents.executor.agent import ExecutorAgent, ExecutorInput, ExecutorOutput


def test_boundary_scores_and_gate_decisions():
    """
    Test exact boundary thresholds:
      - 30  -> LOW, AUTO_EXECUTE
      - 31  -> MEDIUM, SUPERVISOR_REVIEW
      - 60  -> MEDIUM, SUPERVISOR_REVIEW
      - 61  -> HIGH, HUMAN_APPROVAL_REQUIRED
      - 80  -> HIGH, HUMAN_APPROVAL_REQUIRED
      - 81  -> CRITICAL, BLOCKED
      - 100 -> CRITICAL, BLOCKED
    """
    # Boundary 30
    tier, gate, approved, human = DeterministicRiskCalculator.evaluate_tier_and_gate(30)
    assert tier == RiskTier.LOW
    assert gate == GateDecision.AUTO_EXECUTE
    assert approved is True
    assert human is False

    # Boundary 31
    tier, gate, approved, human = DeterministicRiskCalculator.evaluate_tier_and_gate(31)
    assert tier == RiskTier.MEDIUM
    assert gate == GateDecision.SUPERVISOR_REVIEW
    assert approved is True
    assert human is False

    # Boundary 60
    tier, gate, approved, human = DeterministicRiskCalculator.evaluate_tier_and_gate(60)
    assert tier == RiskTier.MEDIUM
    assert gate == GateDecision.SUPERVISOR_REVIEW
    assert approved is True
    assert human is False

    # Boundary 61
    tier, gate, approved, human = DeterministicRiskCalculator.evaluate_tier_and_gate(61)
    assert tier == RiskTier.HIGH
    assert gate == GateDecision.HUMAN_APPROVAL_REQUIRED
    assert approved is False
    assert human is True

    # Boundary 80
    tier, gate, approved, human = DeterministicRiskCalculator.evaluate_tier_and_gate(80)
    assert tier == RiskTier.HIGH
    assert gate == GateDecision.HUMAN_APPROVAL_REQUIRED
    assert approved is False
    assert human is True

    # Boundary 81
    tier, gate, approved, human = DeterministicRiskCalculator.evaluate_tier_and_gate(81)
    assert tier == RiskTier.CRITICAL
    assert gate == GateDecision.BLOCKED
    assert approved is False
    assert human is False

    # Boundary 100
    tier, gate, approved, human = DeterministicRiskCalculator.evaluate_tier_and_gate(100)
    assert tier == RiskTier.CRITICAL
    assert gate == GateDecision.BLOCKED
    assert approved is False
    assert human is False


def test_base_tool_risk_values():
    """
    Verify specified base risk values:
      clear_cache = 8
      restart_service = 22
      scale_service = 25
      rollback_deployment = 47
      restore_configuration = 50
      quarantine_asset = 61
    """
    assert DeterministicRiskCalculator.get_base_tool_risk("clear_cache") == 8
    assert DeterministicRiskCalculator.get_base_tool_risk("restart_service") == 22
    assert DeterministicRiskCalculator.get_base_tool_risk("scale_service") == 25
    assert DeterministicRiskCalculator.get_base_tool_risk("rollback_deployment") == 47
    assert DeterministicRiskCalculator.get_base_tool_risk("restore_configuration") == 50
    assert DeterministicRiskCalculator.get_base_tool_risk("quarantine_asset") == 61


def test_security_event_increases_risk_score():
    """Verify that SECURITY_EVENT adds a significant risk penalty."""
    # 1. Scaling under normal conditions
    score_normal = DeterministicRiskCalculator.calculate_score(
        tool_name="scale_service",
        blast_radius_count=1,
        is_security_event=False,
    )
    assert score_normal == 25

    # 2. Scaling under active security attack (+25 penalty)
    score_security = DeterministicRiskCalculator.calculate_score(
        tool_name="scale_service",
        blast_radius_count=1,
        is_security_event=True,
    )
    assert score_security == 50  # 25 + 25 = 50 -> Escalates to MEDIUM / SUPERVISOR_REVIEW

    # 3. Quarantine under security attack (61 + 25 = 86 -> CRITICAL / BLOCKED)
    score_quarantine_sec = DeterministicRiskCalculator.calculate_score(
        tool_name="quarantine_asset",
        blast_radius_count=1,
        is_security_event=True,
    )
    assert score_quarantine_sec == 86
    tier, gate, approved, _ = DeterministicRiskCalculator.evaluate_tier_and_gate(score_quarantine_sec)
    assert tier == RiskTier.CRITICAL
    assert gate == GateDecision.BLOCKED
    assert approved is False


def test_gate_decision_controls_executor():
    """Verify that the gate decision actually controls the Executor Agent's actuation."""
    async def _test():
        executor = ExecutorAgent()

        # Case 1: LOW / AUTO_EXECUTE -> Execution Proceeds
        input_auto = ExecutorInput(
            correlation_id="c1",
            incident_id="i1",
            plan_id="p1",
            risk_score=25.0,
            is_approved=True,
            policy_decision="PERMIT",
            gate_decision="AUTO_EXECUTE",
        )
        out_auto: ExecutorOutput = await executor.process(input_auto)
        assert out_auto.execution_status == "SUCCESS"
        assert out_auto.actuator_response_code == 200
        assert len(out_auto.actions_executed) > 0

        # Case 2: HIGH / HUMAN_APPROVAL_REQUIRED -> Execution Held
        input_high = ExecutorInput(
            correlation_id="c2",
            incident_id="i2",
            plan_id="p2",
            risk_score=75.0,
            is_approved=False,
            policy_decision="HOLD",
            gate_decision="HUMAN_APPROVAL_REQUIRED",
            requires_human_approval=True,
        )
        out_high: ExecutorOutput = await executor.process(input_high)
        assert out_high.execution_status == "HELD_FOR_APPROVAL"
        assert out_high.actuator_response_code == 403
        assert len(out_high.actions_executed) == 0

        # Case 3: CRITICAL / BLOCKED -> Execution Refused
        input_blocked = ExecutorInput(
            correlation_id="c3",
            incident_id="i3",
            plan_id="p3",
            risk_score=95.0,
            is_approved=False,
            policy_decision="DENY",
            gate_decision="BLOCKED",
        )
        out_blocked: ExecutorOutput = await executor.process(input_blocked)
        assert out_blocked.execution_status == "REFUSED_CRITICAL_RISK"
        assert out_blocked.actuator_response_code == 403

    asyncio.run(_test())


def test_risk_output_schema_structure():
    """Verify RiskOutput contains risk_score, tier, gate_decision, rationale."""
    output = RiskOutput(
        incident_id="INC-test-1",
        correlation_id="corr-test-1",
        plan_id="PLAN-01",
        risk_score=25,
        tier="LOW",
        gate_decision="AUTO_EXECUTE",
        rationale="Scale service base risk is 25",
        is_approved=True,
        requires_human_approval=False,
        evaluated_at="2026-08-25T14:35:00Z",
    )

    data = output.model_dump()
    assert data["risk_score"] == 25
    assert data["tier"] == "LOW"
    assert data["gate_decision"] == "AUTO_EXECUTE"
    assert "rationale" in data


def test_risk_agent_event_bus_wiring():
    """Verify RiskAgent receives on incident.simulation_passed and publishes to incident.risk_approved."""
    async def _test():
        bus = EventBus()
        published_decisions = []
        bus.subscribe("incident.risk_approved", lambda ev: published_decisions.append(ev))

        agent = RiskAgent(event_bus=bus)
        agent.start()

        sim_input = RiskInput(
            correlation_id="wiring-risk-1",
            incident_id="INC-wiring-risk-1",
            plan_id="PLAN-SCALE-01",
            selected_plan={"strategy": "scale_service", "actions": [{"tool": "scale_service"}]},
            blast_radius_count=2,
            is_security_incident=False,
        )

        await bus.publish("incident.simulation_passed", sim_input)

        assert len(published_decisions) == 1
        decision_out: RiskOutput = published_decisions[0]
        assert decision_out.incident_id == "INC-wiring-risk-1"
        assert decision_out.risk_score == 28  # 25 base + (2-1)*3 blast = 28
        assert decision_out.tier == "LOW"
        assert decision_out.gate_decision == "AUTO_EXECUTE"

        agent.stop()

    asyncio.run(_test())
