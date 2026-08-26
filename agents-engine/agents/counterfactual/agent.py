"""
Counterfactual Agent for AEGIS Ω.
Simulation & What-If Analysis: Predicts recovery probability, operational risk, downtime,
and secondary failures for all candidate plans, then ranks them via a deterministic Python algorithm.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Protocol, Tuple
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from runtime.event_bus import EventBus
from runtime.llm import get_gemini_client, GeminiClientWrapper
from observability.telemetry import trace_span

from .models import CounterfactualOutput, PlanSimulationResult
from .simulation import (
    DeterministicPlanRanker,
    HistoricalActionOutcomeStore,
    SecondaryFailurePredictor,
)

logger = logging.getLogger(__name__)


class CounterfactualInput(BaseModel):
    """Input payload for Counterfactual Agent from Planner."""
    correlation_id: str
    incident_id: str
    plan_id: str
    target_asset_id: str
    action_steps: List[Any] = Field(default_factory=list)
    estimated_recovery_time_sec: int = 45
    plans: List[Any] = Field(default_factory=list)
    selected_plan: Optional[Any] = None
    strategy_count: Optional[int] = None
    planned_at: Optional[str] = None


class GeminiCounterfactualSimulatorProtocol(Protocol):
    """Clean interface allowing Gemini to reason about simulation probabilities and failure modes."""

    async def simulate_plan_probabilities(
        self,
        plan_id: str,
        strategy: str,
        target_asset: str,
        actions: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Estimate recovery probability and secondary failure risks (does NOT choose winner)."""
        ...


class GeminiCounterfactualSimulator:
    """
    Gemini wrapper for probabilistic risk estimation.
    Gemini is strictly forbidden from selecting the final remediation plan.
    """

    def __init__(self, llm_wrapper: Optional[GeminiClientWrapper] = None):
        self.llm_wrapper = llm_wrapper or get_gemini_client()
        self.call_count = 0

    async def simulate_plan_probabilities(
        self,
        plan_id: str,
        strategy: str,
        target_asset: str,
        actions: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        self.call_count += 1
        if self.llm_wrapper and self.llm_wrapper.is_configured:
            try:
                actions_summary = json.dumps(actions)
                prompt = (
                    "You are the AEGIS Ω Counterfactual Simulation Oracle.\n"
                    "Predict the recovery probability and failure side-effects of this candidate plan.\n"
                    "NOTE: You are ONLY evaluating probabilities. You do NOT make the final decision.\n\n"
                    f"Plan ID: {plan_id}\n"
                    f"Strategy: {strategy}\n"
                    f"Target Asset: {target_asset}\n"
                    f"Actions: {actions_summary}\n\n"
                    "Respond with a JSON object conforming to:\n"
                    "{\n"
                    "  \"recovery_probability\": 0.90,\n"
                    "  \"risk_category\": \"LOW|MEDIUM|HIGH\",\n"
                    "  \"downtime_estimate\": \"0s|15s|60s\",\n"
                    "  \"secondary_failures\": [\"...\"]\n"
                    "}"
                )
                client = self.llm_wrapper.get_client()
                if hasattr(client, "aio") and hasattr(client.aio, "models"):
                    response = await client.aio.models.generate_content(
                        model=self.llm_wrapper.model_name,
                        contents=prompt,
                    )
                    text = response.text.strip()
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0].strip()
                    return json.loads(text)
            except Exception as e:
                logger.warning(f"Gemini counterfactual simulation fallback: {e}")

        return None


class CounterfactualAgent(BaseAgent[CounterfactualInput, CounterfactualOutput]):
    """
    Counterfactual Agent:
    - Evaluates all candidate plans in pre-execution simulation.
    - Models recovery probability, risk, downtime, and secondary failures.
    - Uses deterministic Python scoring function to rank plans (Gemini never chooses winner).
    - Publishes CounterfactualOutput to 'incident.simulation_passed' for Risk Agent.
    """

    name = "Counterfactual"
    description = "Simulates remediation plans and ranks them via deterministic multi-criteria scoring."
    inbound_topic = "incident.plan_proposed"
    outbound_topic = "incident.simulation_passed"
    input_schema = CounterfactualInput
    output_schema = CounterfactualOutput

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        simulator: Optional[GeminiCounterfactualSimulatorProtocol] = None,
    ):
        super().__init__(event_bus=event_bus)
        self.simulator = simulator or GeminiCounterfactualSimulator()

    async def process(self, input_data: CounterfactualInput) -> CounterfactualOutput:
        """
        Simulate all candidate remediation plans and execute deterministic ranking.
        """
        target_asset = input_data.target_asset_id
        candidate_plans = input_data.plans or []

        # If no plans list was provided, synthesize from selected_plan or action_steps
        if not candidate_plans:
            candidate_plans = [
                {
                    "plan_id": input_data.plan_id or f"PLAN-{input_data.correlation_id[:8]}-DEFAULT",
                    "strategy": "scale",
                    "risk_estimate": "LOW",
                    "downtime_estimate": "0s",
                    "confidence": 90,
                    "actions": input_data.action_steps,
                }
            ]

        # Step 1: Simulate every candidate plan
        simulated_results: List[PlanSimulationResult] = []

        for p in candidate_plans:
            plan_dict = p if isinstance(p, dict) else (p.model_dump() if hasattr(p, "model_dump") else {})
            pid = plan_dict.get("plan_id", f"PLAN-{target_asset}")
            strat = plan_dict.get("strategy", "scale")
            risk_raw = plan_dict.get("risk_estimate", "LOW")
            downtime_raw = str(plan_dict.get("downtime_estimate", "0s"))
            conf = float(plan_dict.get("confidence", 85)) / 100.0
            actions = plan_dict.get("actions", [])

            # Extract first tool name if available
            first_tool = "scale_service"
            if actions and isinstance(actions[0], dict):
                first_tool = actions[0].get("tool", actions[0].get("action_type", "scale_service"))
            elif actions and hasattr(actions[0], "tool"):
                first_tool = getattr(actions[0], "tool", "scale_service")

            # Check historical benchmark
            benchmark = HistoricalActionOutcomeStore.get_benchmark(first_tool)

            # Predict secondary failure side-effects
            side_effects = SecondaryFailurePredictor.predict_side_effects(
                strategy=strat,
                target_asset=target_asset,
                affected_systems=[],
            )

            # Optional Gemini probabilistic assessment
            gemini_eval = await self.simulator.simulate_plan_probabilities(
                plan_id=pid,
                strategy=strat,
                target_asset=target_asset,
                actions=actions if isinstance(actions, list) else [],
            )

            if gemini_eval:
                recovery_prob = float(gemini_eval.get("recovery_probability", conf))
                risk_est = str(gemini_eval.get("risk_category", risk_raw)).upper()
                downtime_est = str(gemini_eval.get("downtime_estimate", downtime_raw))
                if "secondary_failures" in gemini_eval and gemini_eval["secondary_failures"]:
                    side_effects.extend(gemini_eval["secondary_failures"])
            else:
                recovery_prob = benchmark["base_recovery_prob"]
                risk_est = risk_raw.upper()
                downtime_est = downtime_raw

            simulated_results.append(
                PlanSimulationResult(
                    plan_id=pid,
                    predicted_recovery_probability=recovery_prob,
                    predicted_risk=risk_est,
                    predicted_downtime=downtime_est,
                    possible_secondary_failures=side_effects,
                )
            )

        # Step 2: Deterministic Ranking in Python (Gemini NEVER chooses the final plan)
        ranked_plans, winner_plan_id, justification = DeterministicPlanRanker.rank_plans(
            simulation_results=simulated_results,
        )

        # Step 3: Identify winning plan object for downstream execution
        winning_plan_obj = None
        for p in candidate_plans:
            p_id = p.get("plan_id") if isinstance(p, dict) else getattr(p, "plan_id", None)
            if p_id == winner_plan_id:
                winning_plan_obj = p
                break

        if winning_plan_obj is None and candidate_plans:
            winning_plan_obj = candidate_plans[0]

        return CounterfactualOutput(
            incident_id=input_data.incident_id,
            correlation_id=input_data.correlation_id,
            plan_id=winner_plan_id,
            ranked_plans=ranked_plans,
            selected_plan_id=winner_plan_id,
            justification=justification,
            simulation_passed=True,
            predicted_side_effects=ranked_plans[0].possible_secondary_failures if ranked_plans else [],
            alternative_paths_evaluated=len(ranked_plans),
            selected_plan=winning_plan_obj,
            simulated_at=datetime.now(timezone.utc).isoformat(),
        )
