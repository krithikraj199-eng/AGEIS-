"""
Unit and Integration Tests for AEGIS Ω Prediction Engine.
Tests:
  - Rolling window metric trending
  - Proactive PREDICTED_INCIDENT generation BEFORE hard threshold is crossed:
      Disk usage: 70 -> 75 -> 80 -> 85 -> 89 with threshold 90 -> Prediction fires BEFORE 90.
  - False positive noise rejection
  - Semantic and Procedural memory synthesis
  - Proven procedural strategy reuse across the remediation pipeline:
      Prediction -> Planner -> Counterfactual -> Risk -> Executor -> Verifier
"""

import asyncio
from typing import Any, Dict, List

from memory.storage import InMemoryStorageBackend
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.procedural import ProceduralMemory
from tools.client import MockDigitalWorldClient
from tools.registry import ToolRegistry
from agents.prediction.forecaster import DeterministicTrendForecaster
from agents.prediction.models import PredictionInput, PredictionOutput
from agents.prediction.agent import PredictionAgent
from agents.planner.agent import PlannerAgent, PlannerInput, PlannerOutput
from agents.counterfactual.agent import CounterfactualAgent
from agents.risk.agent import RiskAgent
from agents.executor.agent import ExecutorAgent
from agents.verifier.agent import VerifierAgent


def test_prediction_fires_before_hard_threshold():
    """
    CRITICAL SPECIFICATION TEST:
    Disk usage: 70, 75, 80, 85, 89
    Hard threshold: 90
    Prediction MUST fire BEFORE 90.
    """
    async def _test():
        forecaster = DeterministicTrendForecaster(
            prediction_horizon_sec=120.0,
            thresholds={"disk_usage": 90.0},
        )
        agent = PredictionAgent(forecaster=forecaster)

        readings = [70.0, 75.0, 80.0, 85.0, 89.0]
        prediction_emitted = None

        for val in readings:
            assert val < 90.0, "Input reading must strictly be below hard threshold"
            inp = PredictionInput(
                asset_id="STORAGE-01",
                metric_name="disk_usage",
                value=val,
                threshold=90.0,
            )
            out = await agent.process(inp)
            if out is not None:
                prediction_emitted = out

        # Assert that prediction fired before crossing 90
        assert prediction_emitted is not None
        assert prediction_emitted.status == "PREDICTED_INCIDENT"
        assert prediction_emitted.forecast.current_value == 89.0
        assert prediction_emitted.forecast.hard_threshold == 90.0
        assert prediction_emitted.forecast.is_breach_imminent is True
        assert prediction_emitted.forecast.projected_seconds_to_breach <= 120.0
        assert "Imminent breach on STORAGE-01" in prediction_emitted.root_cause

    asyncio.run(_test())


def test_flat_and_declining_metrics_do_not_trigger_false_positives():
    """Verify that flat or downward trending metrics do not trigger predictions."""
    async def _test():
        forecaster = DeterministicTrendForecaster(thresholds={"disk_usage": 90.0})
        agent = PredictionAgent(forecaster=forecaster)

        # 1. Flat metric stream
        flat_stream = [45.0, 45.0, 46.0, 45.0, 45.0]
        for v in flat_stream:
            out = await agent.process(PredictionInput(asset_id="NODE-01", metric_name="disk_usage", value=v))
            assert out is None

        # 2. Declining metric stream
        declining_stream = [85.0, 80.0, 75.0, 70.0, 65.0]
        for v in declining_stream:
            out = await agent.process(PredictionInput(asset_id="NODE-02", metric_name="disk_usage", value=v))
            assert out is None

    asyncio.run(_test())


def test_procedural_strategy_reuse_in_prediction_and_planner():
    """
    Verify that a successful procedural strategy (e.g. clear_cache) is queried
    by PredictionAgent and reused by PlannerAgent when formulating proactive remediation.
    """
    async def _test():
        store = InMemoryStorageBackend()
        proc_mem = ProceduralMemory(store=store)
        sem_mem = SemanticMemory(store=store)

        # Seed Procedural Memory with proven clear_cache strategy on STORAGE-01
        sig = "STORAGE-01:DISK_USAGE_SATURATION"
        proc_mem.record_action_outcome(sig, "clear_cache", success=True)
        proc_mem.record_action_outcome(sig, "clear_cache", success=True)
        proc_mem.record_action_outcome(sig, "clear_cache", success=True)

        # 1. Trigger Prediction
        forecaster = DeterministicTrendForecaster(thresholds={"disk_usage": 90.0})
        pred_agent = PredictionAgent(
            forecaster=forecaster,
            proc_mem=proc_mem,
            sem_mem=sem_mem,
        )

        readings = [70.0, 75.0, 80.0, 85.0, 89.0]
        pred_out = None
        for v in readings:
            out = await pred_agent.process(PredictionInput(asset_id="STORAGE-01", metric_name="disk_usage", value=v))
            if out:
                pred_out = out

        assert pred_out is not None
        assert pred_out.predicted_incident.recommended_strategy == "clear_cache"

        # 2. Feed PredictionOutput into PlannerAgent
        planner = PlannerAgent(procedural_memory=proc_mem)
        planner_inp = PlannerInput(
            correlation_id=pred_out.correlation_id,
            incident_id=pred_out.incident_id,
            root_asset_id=pred_out.root_asset_id,
            root_cause=pred_out.root_cause,
            primary_failure_cause=pred_out.primary_failure_cause,
            affected_systems=pred_out.affected_systems,
            confidence_score=pred_out.confidence_score,
        )

        plan_out: PlannerOutput = await planner.process(planner_inp)

        # 3. Assert Planner selects clear_cache with boosted confidence
        assert plan_out.selected_plan.strategy == "clear_cache" or any(a.action_type == "clear_cache" for a in plan_out.action_steps)
        assert plan_out.selected_plan.confidence >= 90

    asyncio.run(_test())


def test_end_to_end_proactive_remediation_pipeline():
    """
    Test full proactive remediation pipeline:
    Prediction -> Planner -> Counterfactual -> Risk -> Executor -> Verifier
    """
    async def _test():
        store = InMemoryStorageBackend()
        proc_mem = ProceduralMemory(store=store)
        mock_client = MockDigitalWorldClient()
        tool_registry = ToolRegistry(client=mock_client)

        # 1. Prediction fires
        forecaster = DeterministicTrendForecaster(thresholds={"disk_usage": 90.0})
        pred_agent = PredictionAgent(forecaster=forecaster, proc_mem=proc_mem)

        pred_out = None
        for val in [70.0, 75.0, 80.0, 85.0, 89.0]:
            out = await pred_agent.process(PredictionInput(asset_id="STORAGE-01", metric_name="disk_usage", value=val))
            if out:
                pred_out = out

        assert pred_out is not None

        # 2. Planner generates proactive plan
        planner = PlannerAgent(procedural_memory=proc_mem)
        plan_out = await planner.process(
            PlannerInput(
                correlation_id=pred_out.correlation_id,
                incident_id=pred_out.incident_id,
                root_asset_id=pred_out.root_asset_id,
                root_cause=pred_out.root_cause,
                primary_failure_cause=pred_out.primary_failure_cause,
                affected_systems=pred_out.affected_systems,
            )
        )
        assert plan_out.selected_plan is not None

        # 3. Counterfactual simulates
        cf_agent = CounterfactualAgent()
        from agents.counterfactual.agent import CounterfactualInput
        cf_out = await cf_agent.process(
            CounterfactualInput(
                correlation_id=plan_out.correlation_id,
                incident_id=plan_out.incident_id,
                plan_id=plan_out.plan_id,
                target_asset_id=plan_out.target_asset_id,
                plans=[p.model_dump() for p in plan_out.plans],
                selected_plan=plan_out.selected_plan.model_dump(),
            )
        )
        assert cf_out.selected_plan_id is not None

        # 4. Risk gates
        risk_agent = RiskAgent()
        from agents.risk.agent import RiskInput
        risk_out = await risk_agent.process(
            RiskInput(
                correlation_id=cf_out.correlation_id,
                incident_id=cf_out.incident_id,
                plan_id=cf_out.selected_plan_id,
                selected_plan=cf_out.selected_plan,
                ranked_plans=cf_out.ranked_plans,
                simulation_passed=True,
            )
        )
        assert risk_out.gate_decision in ["AUTO_EXECUTE", "SUPERVISOR_REVIEW"]

        # 5. Executor runs
        executor = ExecutorAgent(registry=tool_registry)
        from agents.executor.agent import ExecutorInput
        sel_plan_dict = risk_out.selected_plan if isinstance(risk_out.selected_plan, dict) else (risk_out.selected_plan.model_dump() if hasattr(risk_out.selected_plan, "model_dump") else {})
        actions_list = sel_plan_dict.get("actions", [])
        exec_out = await executor.process(
            ExecutorInput(
                correlation_id=risk_out.correlation_id,
                incident_id=risk_out.incident_id,
                plan_id=risk_out.plan_id,
                risk_score=risk_out.risk_score,
                tier=risk_out.tier.value if hasattr(risk_out.tier, "value") else str(risk_out.tier),
                gate_decision=risk_out.gate_decision.value if hasattr(risk_out.gate_decision, "value") else str(risk_out.gate_decision),
                actions_to_execute=actions_list,
                selected_plan=risk_out.selected_plan,
            )
        )
        assert exec_out.execution_status == "SUCCESS"

        # 6. Verifier audits
        verifier = VerifierAgent()
        from agents.verifier.agent import VerifierInput
        ver_out = await verifier.process(
            VerifierInput(
                correlation_id=exec_out.correlation_id,
                incident_id=exec_out.incident_id,
                plan_id=exec_out.plan_id,
                metric_name="disk_usage",
                before_value=89.0,
                after_value=42.0,
                target_threshold=90.0,
            )
        )
        assert ver_out.status in ["SUCCESS", "PASSED"] or getattr(ver_out.status, "value", "") in ["SUCCESS", "PASSED"]
        assert ver_out.after == 42.0

    asyncio.run(_test())
