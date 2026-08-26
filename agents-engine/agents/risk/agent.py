"""
Risk Agent for AEGIS Ω.
Governance & Risk Scoring: Computes 0-100 deterministic risk score and enforces execution gate controls.
This component is 100% deterministic and does NOT use Gemini.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from runtime.event_bus import EventBus
from observability.telemetry import trace_span

from .calculator import DeterministicRiskCalculator
from .models import GateDecision, RiskOutput, RiskTier

logger = logging.getLogger(__name__)


class RiskInput(BaseModel):
    """Input payload for Risk Agent from Counterfactual."""
    correlation_id: str
    incident_id: str
    plan_id: str
    simulation_passed: bool = True
    predicted_side_effects: List[str] = Field(default_factory=list)
    alternative_paths_evaluated: int = 0
    ranked_plans: List[Any] = Field(default_factory=list)
    selected_plan_id: Optional[str] = None
    justification: Optional[str] = None
    selected_plan: Optional[Any] = None
    simulated_at: Optional[str] = None
    classification: Optional[str] = None
    is_security_incident: Optional[bool] = False
    blast_radius_count: Optional[int] = 1


class RiskAgent(BaseAgent[RiskInput, RiskOutput]):
    """
    Risk Agent:
    - 100% deterministic calculation in pure Python (no Gemini).
    - Base risk table: clear_cache=8, restart=22, scale=25, rollback=47, restore_config=50, quarantine=61.
    - Adjusts for blast radius and security classification penalties.
    - Maps score to 4 tiers: LOW (0-30), MEDIUM (31-60), HIGH (61-80), CRITICAL (81-100).
    - Gate decisions directly control the Executor: AUTO_EXECUTE, SUPERVISOR_REVIEW, HUMAN_APPROVAL_REQUIRED, BLOCKED.
    - Publishes RiskOutput to 'incident.risk_approved' for Executor Agent.
    """

    name = "Risk"
    description = "Calculates deterministic 0-100 risk score and enforces multi-tier execution gates."
    inbound_topic = "incident.simulation_passed"
    outbound_topic = "incident.risk_approved"
    input_schema = RiskInput
    output_schema = RiskOutput

    def _extract_primary_tool(self, input_data: RiskInput) -> str:
        """Extract primary remediation tool name from selected plan."""
        plan_obj = input_data.selected_plan

        if isinstance(plan_obj, dict):
            actions = plan_obj.get("actions", [])
            if actions and isinstance(actions[0], dict):
                return actions[0].get("tool", actions[0].get("action_type", "scale_service"))
            strat = plan_obj.get("strategy", "scale_service")
            if not strat.endswith("_service") and not strat.endswith("_deployment") and not strat.endswith("_configuration") and not strat.endswith("_asset") and not strat.endswith("_cache"):
                strat = f"{strat}_service"
            return strat
        elif hasattr(plan_obj, "actions"):
            actions = getattr(plan_obj, "actions", [])
            if actions and hasattr(actions[0], "tool"):
                return getattr(actions[0], "tool", "scale_service")
        elif hasattr(plan_obj, "strategy"):
            strat = getattr(plan_obj, "strategy", "scale_service")
            return strat

        return "scale_service"

    async def process(self, input_data: RiskInput) -> RiskOutput:
        """
        Execute deterministic risk evaluation and gate decision.
        """
        primary_tool = self._extract_primary_tool(input_data)
        is_security = bool(input_data.is_security_incident or (str(input_data.classification).upper() == "SECURITY_EVENT"))
        blast_count = int(input_data.blast_radius_count or 1)

        # Step 1: Calculate deterministic 0-100 risk score in pure Python
        risk_score = DeterministicRiskCalculator.calculate_score(
            tool_name=primary_tool,
            blast_radius_count=blast_count,
            is_security_event=is_security,
        )

        # Step 2: Evaluate RiskTier and GateDecision
        tier, gate_decision, is_approved, requires_human = DeterministicRiskCalculator.evaluate_tier_and_gate(
            score=risk_score,
        )

        # Step 3: Formulate deterministic rationale
        base_val = DeterministicRiskCalculator.get_base_tool_risk(primary_tool)
        rationale = (
            f"Risk Score {risk_score}/100 [{tier.value}]: Base tool '{primary_tool}' risk={base_val}, "
            f"blast radius count={blast_count} (+{min(15, max(0, (blast_count - 1) * 3))}), "
            f"security event penalty=+{25 if is_security else 0}. "
            f"Gate Decision: {gate_decision.value}."
        )

        return RiskOutput(
            incident_id=input_data.incident_id,
            correlation_id=input_data.correlation_id,
            plan_id=input_data.plan_id or "PLAN-DEFAULT",
            risk_score=risk_score,
            tier=tier.value,
            gate_decision=gate_decision.value,
            rationale=rationale,
            is_approved=is_approved,
            requires_human_approval=requires_human,
            policy_decision="PERMIT" if is_approved else "HOLD",
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            selected_plan=input_data.selected_plan,
        )
