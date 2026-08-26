"""
Unit Tests for Planner Agent in AEGIS Ω.
Tests remediation strategy diversity (2-4 distinct plans), strict tool whitelist enforcement,
rejection of unknown tools, rollback method verification, and zero direct execution.
"""

import asyncio
from typing import Any, Dict, List

from runtime.event_bus import EventBus
from agents.planner.models import (
    ALLOWED_TOOL_NAMES,
    AllowedTool,
    PlannerOutput,
    RemediationPlan,
)
from agents.planner.validator import PlanValidator
from agents.planner.agent import (
    PlannerAgent,
    PlannerInput,
    GeminiPlanGeneratorProtocol,
)


class MockPlanGenerator:
    """Mock Gemini plan generator for deterministic unit testing."""

    def __init__(self, raw_plans: List[Dict[str, Any]]):
        self.raw_plans = raw_plans
        self.call_count = 0

    async def generate_plans(
        self,
        root_cause: str,
        target_asset: str,
        affected_systems: List[str],
        blast_radius: Any,
    ) -> List[Dict[str, Any]]:
        self.call_count += 1
        return self.raw_plans


def test_strategy_diversity_and_plan_count():
    """
    Verify that at least 3 distinct strategies are generated across 2-4 plans.
    """
    async def _test():
        agent = PlannerAgent()

        input_data = PlannerInput(
            correlation_id="plan-test-1",
            incident_id="INC-plan-1",
            root_asset_id="DATABASE-01",
            root_cause="Database connection pool exhausted",
            affected_systems=["DATABASE-01", "AUTH-01", "API-01"],
            blast_radius={"blast_radius_count": 3},
        )

        output: PlannerOutput = await agent.process(input_data)

        # Asserts 2 to 4 plans
        assert 2 <= len(output.plans) <= 4
        assert output.strategy_count == len(output.plans)

        # Asserts distinct strategies
        strategies = [p.strategy for p in output.plans]
        assert len(set(strategies)) >= 3
        assert len(set(strategies)) == len(strategies)  # No duplicate strategies!

    asyncio.run(_test())


def test_unknown_tools_are_rejected_and_sanitized():
    """
    Verify that unknown tools (e.g. 'nuke_database', 'delete_server') are rejected.
    """
    raw_malicious_plans = [
        {
            "plan_id": "PLAN-BAD-1",
            "name": "Nuke Database Plan",
            "strategy": "destructive_kill",
            "actions": [
                {"step": 1, "tool": "nuke_database", "target_asset": "DATABASE-01", "parameters": {}}
            ],
            "expected_result": "Total wipeout",
            "estimated_recovery_seconds": 10,
            "risk_estimate": "CRITICAL",
            "downtime_estimate": "Permanent",
            "blast_radius": "Cluster-wide",
            "confidence": 90,
            "rollback_method": "No rollback possible",
        },
        {
            "plan_id": "PLAN-BAD-2",
            "name": "Drop Tables Plan",
            "strategy": "drop_tables",
            "actions": [
                {"step": 1, "tool": "drop_tables", "target_asset": "DATABASE-01", "parameters": {}}
            ],
            "expected_result": "Drop table schema",
            "estimated_recovery_seconds": 10,
            "risk_estimate": "HIGH",
            "downtime_estimate": "None",
            "blast_radius": "DB",
            "confidence": 80,
            "rollback_method": "Restore from cold tape backup",
        },
    ]

    async def _test():
        mock_gen = MockPlanGenerator(raw_plans=raw_malicious_plans)
        agent = PlannerAgent(generator=mock_gen)

        input_data = PlannerInput(
            correlation_id="sec-reject-1",
            incident_id="INC-sec-reject-1",
            root_asset_id="DATABASE-01",
            root_cause="Database pool starvation",
        )

        output: PlannerOutput = await agent.process(input_data)

        # The malicious plans MUST be rejected and replaced with safe verified fallback plans
        for plan in output.plans:
            for action in plan.actions:
                assert action.tool in ALLOWED_TOOL_NAMES
                assert action.tool not in ["nuke_database", "drop_tables"]

        assert len(output.plans) >= 2

    asyncio.run(_test())


def test_malformed_plans_without_rollback_are_rejected():
    """Verify that plans with missing rollback method or empty actions are rejected."""
    raw_invalid_plans = [
        {
            "plan_id": "PLAN-INVALID-1",
            "name": "Missing Rollback Plan",
            "strategy": "restart",
            "actions": [
                {"step": 1, "tool": "restart_service", "target_asset": "DATABASE-01", "parameters": {}}
            ],
            "expected_result": "Reboot",
            "estimated_recovery_seconds": 30,
            "risk_estimate": "LOW",
            "downtime_estimate": "10s",
            "blast_radius": "Local",
            "confidence": 85,
            "rollback_method": "",  # Empty rollback
        }
    ]

    validated = PlanValidator.validate_and_filter_plans(
        raw_plans=raw_invalid_plans,
        target_asset="DATABASE-01",
        blast_radius={},
        correlation_id="corr-inv-1",
    )

    # Empty rollback was rejected, so safe verified plans were supplied
    for p in validated:
        assert p.rollback_method is not None
        assert len(p.rollback_method.strip()) >= 5


def test_every_plan_contains_rollback_information():
    """Verify that all plans in output contain detailed, actionable rollback procedures."""
    async def _test():
        agent = PlannerAgent()

        input_data = PlannerInput(
            correlation_id="rb-test-1",
            incident_id="INC-rb-1",
            root_asset_id="DATABASE-01",
            root_cause="Connection pool exhaustion",
        )

        output: PlannerOutput = await agent.process(input_data)

        for plan in output.plans:
            assert hasattr(plan, "rollback_method")
            assert len(plan.rollback_method) > 10
            assert "rollback" in plan.rollback_method.lower() or "restore" in plan.rollback_method.lower() or "scale" in plan.rollback_method.lower()

    asyncio.run(_test())


def test_planner_agent_event_bus_wiring():
    """Verify PlannerAgent receives on incident.root_cause and publishes to incident.plan_proposed."""
    async def _test():
        bus = EventBus()
        published_plans = []
        bus.subscribe("incident.plan_proposed", lambda ev: published_plans.append(ev))

        agent = PlannerAgent(event_bus=bus)
        agent.start()

        rc_input = PlannerInput(
            correlation_id="wiring-plan-1",
            incident_id="INC-wiring-plan-1",
            root_asset_id="DATABASE-01",
            root_cause="Database pool starvation",
        )

        await bus.publish("incident.root_cause", rc_input)

        assert len(published_plans) == 1
        plan_out: PlannerOutput = published_plans[0]
        assert plan_out.incident_id == "INC-wiring-plan-1"
        assert len(plan_out.plans) >= 2
        assert plan_out.selected_plan is not None

        agent.stop()

    asyncio.run(_test())
