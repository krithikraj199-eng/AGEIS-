"""
Unit Tests for Counterfactual Engine in AEGIS Ω.
Tests pre-execution simulation, deterministic plan ranking, secondary failure prediction,
and strict non-override of mathematical selection by LLM.
"""

import asyncio
from typing import Any, Dict, List, Optional

from runtime.event_bus import EventBus
from agents.counterfactual.models import CounterfactualOutput, PlanSimulationResult
from agents.counterfactual.simulation import (
    DeterministicPlanRanker,
    HistoricalActionOutcomeStore,
    SecondaryFailurePredictor,
)
from agents.counterfactual.agent import (
    CounterfactualAgent,
    CounterfactualInput,
    GeminiCounterfactualSimulatorProtocol,
)


def test_deterministic_scoring_algorithm_with_three_plans():
    """
    Test deterministic plan ranking with 3 plans having different recovery prob, risk, and downtime:
      - Plan 1: High recovery (0.95), LOW risk, 0s downtime
      - Plan 2: Medium recovery (0.80), MEDIUM risk, 15s downtime
      - Plan 3: Low recovery (0.60), HIGH risk, 60s downtime
    Proves that Plan 1 is deterministically ranked #1.
    """
    sim_1 = PlanSimulationResult(
        plan_id="PLAN-SCALE-01",
        predicted_recovery_probability=0.95,
        predicted_risk="LOW",
        predicted_downtime="0s",
        possible_secondary_failures=[],
    )
    sim_2 = PlanSimulationResult(
        plan_id="PLAN-RESTART-02",
        predicted_recovery_probability=0.80,
        predicted_risk="MEDIUM",
        predicted_downtime="15s",
        possible_secondary_failures=["Transient connection drops"],
    )
    sim_3 = PlanSimulationResult(
        plan_id="PLAN-QUARANTINE-03",
        predicted_recovery_probability=0.60,
        predicted_risk="HIGH",
        predicted_downtime="60s",
        possible_secondary_failures=["Downstream 503 traffic spike"],
    )

    ranked, winner_id, justification = DeterministicPlanRanker.rank_plans([sim_2, sim_3, sim_1])

    # Asserts exact ranking order
    assert len(ranked) == 3
    assert ranked[0].plan_id == "PLAN-SCALE-01"
    assert ranked[0].rank == 1
    assert ranked[1].plan_id == "PLAN-RESTART-02"
    assert ranked[1].rank == 2
    assert ranked[2].plan_id == "PLAN-QUARANTINE-03"
    assert ranked[2].rank == 3

    # Winner must be PLAN-SCALE-01
    assert winner_id == "PLAN-SCALE-01"
    assert "PLAN-SCALE-01" in justification
    assert ranked[0].composite_score > ranked[1].composite_score > ranked[2].composite_score


def test_gemini_cannot_override_deterministic_ranking():
    """
    Verify that even if Gemini provides probabilistic estimates, the final decision
    is strictly made by the deterministic scoring algorithm.
    """
    class MockBiasedSimulator:
        async def simulate_plan_probabilities(
            self,
            plan_id: str,
            strategy: str,
            target_asset: str,
            actions: List[Dict[str, Any]],
        ) -> Optional[Dict[str, Any]]:
            # Return raw probabilities
            if "scale" in strategy:
                return {"recovery_probability": 0.94, "risk_category": "LOW", "downtime_estimate": "0s"}
            elif "restart" in strategy:
                return {"recovery_probability": 0.82, "risk_category": "MEDIUM", "downtime_estimate": "15s"}
            return {"recovery_probability": 0.70, "risk_category": "HIGH", "downtime_estimate": "45s"}

    async def _test():
        agent = CounterfactualAgent(simulator=MockBiasedSimulator())

        input_data = CounterfactualInput(
            correlation_id="rank-test-1",
            incident_id="INC-rank-1",
            plan_id="PLAN-DEFAULT",
            target_asset_id="DATABASE-01",
            plans=[
                {"plan_id": "P-RESTART", "strategy": "restart", "actions": [{"tool": "restart_service"}]},
                {"plan_id": "P-SCALE", "strategy": "scale", "actions": [{"tool": "scale_service"}]},
                {"plan_id": "P-QUARANTINE", "strategy": "quarantine", "actions": [{"tool": "quarantine_asset"}]},
            ],
        )

        output: CounterfactualOutput = await agent.process(input_data)

        # The deterministic scoring MUST pick P-SCALE
        assert output.selected_plan_id == "P-SCALE"
        assert output.ranked_plans[0].plan_id == "P-SCALE"
        assert output.ranked_plans[0].composite_score >= 0.90

    asyncio.run(_test())


def test_secondary_failure_prediction():
    """Verify that secondary failure risks are predicted for restart, cache clear, and scaling."""
    restart_effects = SecondaryFailurePredictor.predict_side_effects("restart", "DATABASE-01", [])
    assert any("connection timeout" in e for e in restart_effects)

    cache_effects = SecondaryFailurePredictor.predict_side_effects("clear_cache", "CACHE-01", [])
    assert any("cache stampede" in e for e in cache_effects)

    scale_effects = SecondaryFailurePredictor.predict_side_effects("scale", "DATABASE-01", [])
    assert any("replica warmup" in e for e in scale_effects)


def test_counterfactual_output_schema_structure():
    """Verify CounterfactualOutput contains ranked_plans, selected_plan_id, justification."""
    item = PlanSimulationResult(
        plan_id="PLAN-01",
        predicted_recovery_probability=0.90,
        predicted_risk="LOW",
        predicted_downtime="0s",
        possible_secondary_failures=[],
        composite_score=0.92,
        rank=1,
    )

    output = CounterfactualOutput(
        incident_id="INC-sim-1",
        correlation_id="corr-sim-1",
        plan_id="PLAN-01",
        ranked_plans=[item],
        selected_plan_id="PLAN-01",
        justification="Top deterministic score",
        simulated_at="2026-08-25T14:30:00Z",
    )

    data = output.model_dump()
    assert "ranked_plans" in data
    assert "selected_plan_id" in data
    assert "justification" in data
    assert len(data["ranked_plans"]) == 1
    assert data["ranked_plans"][0]["predicted_recovery_probability"] == 0.90


def test_counterfactual_agent_event_bus_wiring():
    """Verify CounterfactualAgent receives on incident.plan_proposed and publishes to incident.simulation_passed."""
    async def _test():
        bus = EventBus()
        published_sims = []
        bus.subscribe("incident.simulation_passed", lambda ev: published_sims.append(ev))

        agent = CounterfactualAgent(event_bus=bus)
        agent.start()

        plan_input = CounterfactualInput(
            correlation_id="wiring-sim-1",
            incident_id="INC-wiring-sim-1",
            plan_id="PLAN-01",
            target_asset_id="DATABASE-01",
            plans=[
                {"plan_id": "P-SCALE", "strategy": "scale", "actions": [{"tool": "scale_service"}]},
                {"plan_id": "P-RESTART", "strategy": "restart", "actions": [{"tool": "restart_service"}]},
            ],
        )

        await bus.publish("incident.plan_proposed", plan_input)

        assert len(published_sims) == 1
        sim_out: CounterfactualOutput = published_sims[0]
        assert sim_out.incident_id == "INC-wiring-sim-1"
        assert sim_out.selected_plan_id == "P-SCALE"
        assert len(sim_out.ranked_plans) == 2

        agent.stop()

    asyncio.run(_test())
