"""
Planner Agent for AEGIS Ω.
Remediation Planning: Generates 2-4 distinct remediation plans using strictly whitelisted tools,
verifies rollback procedures, and prevents unauthorized execution.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Protocol
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from runtime.event_bus import EventBus
from runtime.llm import get_gemini_client, GeminiClientWrapper
from observability.telemetry import trace_span

from .models import (
    ALLOWED_TOOL_NAMES,
    ActionStep,
    PlannerOutput,
    RemediationAction,
    RemediationPlan,
)
from .validator import PlanValidator

logger = logging.getLogger(__name__)


class PlannerInput(BaseModel):
    """Input payload for Planner Agent from Root Cause."""
    correlation_id: str
    incident_id: str
    root_asset_id: str
    root_cause: Optional[str] = None
    primary_failure_cause: Optional[str] = None
    confidence: Optional[float] = None
    confidence_score: Optional[float] = 0.85
    affected_systems: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    classification: Optional[str] = None
    blast_radius: Optional[Any] = None
    discrepancy_flag: Optional[bool] = False
    discrepancy_details: Optional[str] = None
    causal_chain: List[str] = Field(default_factory=list)
    diagnosed_at: str = ""
    excluded_plan_ids: List[str] = Field(default_factory=list)


class GeminiPlanGeneratorProtocol(Protocol):
    """Clean interface for Gemini remediation plan generation."""

    async def generate_plans(
        self,
        root_cause: str,
        target_asset: str,
        affected_systems: List[str],
        blast_radius: Any,
    ) -> List[Dict[str, Any]]:
        """Generate 2-4 distinct remediation plans."""
        ...


class GeminiPlanGenerator:
    """
    Gemini wrapper for generating structured remediation plans.
    Strictly instructs model to use only whitelisted tools and diverse strategies.
    """

    def __init__(self, llm_wrapper: Optional[GeminiClientWrapper] = None):
        self.llm_wrapper = llm_wrapper or get_gemini_client()
        self.call_count = 0

    async def generate_plans(
        self,
        root_cause: str,
        target_asset: str,
        affected_systems: List[str],
        blast_radius: Any,
    ) -> List[Dict[str, Any]]:
        self.call_count += 1
        if self.llm_wrapper and self.llm_wrapper.is_configured:
            try:
                allowed_tools_str = ", ".join(sorted(list(ALLOWED_TOOL_NAMES)))
                prompt = (
                    "You are the AEGIS Ω Incident Remediation Architect.\n"
                    "Formulate 2 to 4 DISTINCT remediation strategies targeting the diagnosed root cause.\n"
                    "DO NOT generate minor variations of the same action.\n"
                    f"Diagnosed Cause: {root_cause}\n"
                    f"Target Asset: {target_asset}\n"
                    f"Affected Systems: {affected_systems}\n\n"
                    f"ALLOWED TOOL NAMES ONLY: [{allowed_tools_str}]\n"
                    "Possible distinct strategies: restart, scale, rollback, clear_cache, quarantine, restore_configuration.\n\n"
                    "Respond with a JSON array conforming to:\n"
                    "[\n"
                    "  {\n"
                    "    \"plan_id\": \"PLAN-01-STRATEGY\",\n"
                    "    \"name\": \"Description of Plan\",\n"
                    "    \"strategy\": \"scale|restart|rollback|clear_cache|quarantine|restore_configuration\",\n"
                    "    \"actions\": [{\"step\": 1, \"tool\": \"allowed_tool_name\", \"target_asset\": \"...\", \"parameters\": {}}],\n"
                    "    \"expected_result\": \"...\",\n"
                    "    \"estimated_recovery_seconds\": 45,\n"
                    "    \"risk_estimate\": \"LOW|MEDIUM|HIGH\",\n"
                    "    \"downtime_estimate\": \"...\",\n"
                    "    \"blast_radius\": \"...\",\n"
                    "    \"confidence\": 90,\n"
                    "    \"rollback_method\": \"Specific steps to rollback if verification fails\"\n"
                    "  }\n"
                    "]"
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
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        return parsed
            except Exception as e:
                logger.warning(f"Gemini plan generation fallback: {e}")

        # Fallback to empty list so deterministic validator supplies verified plans
        return []


class PlannerAgent(BaseAgent[PlannerInput, PlannerOutput]):
    """
    Planner Agent:
    - Synthesizes 2-4 distinct remediation strategies.
    - Validates strict tool whitelist (rejects unknown tools).
    - Enforces mandatory rollback methods.
    - Does NOT execute actions directly.
    - Publishes PlannerOutput to 'incident.plan_proposed' for Counterfactual Agent.
    """

    name = "Planner"
    description = "Formulates 2-4 distinct, validated remediation plans with strict tool controls."
    inbound_topic = "incident.root_cause"
    outbound_topic = "incident.plan_proposed"
    input_schema = PlannerInput
    output_schema = PlannerOutput

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        generator: Optional[GeminiPlanGeneratorProtocol] = None,
        procedural_memory: Optional[Any] = None,
    ):
        super().__init__(event_bus=event_bus)
        self.generator = generator or GeminiPlanGenerator()
        self.procedural_memory = procedural_memory

    async def process(self, input_data: PlannerInput) -> PlannerOutput:
        """
        Generate and validate 2-4 distinct remediation plans, biasing selection if procedural memory qualifies.
        """
        target_asset = input_data.root_asset_id
        cause = input_data.root_cause or input_data.primary_failure_cause or f"Anomaly on {target_asset}"

        # Step 1: Call Gemini or Generator for candidate plans
        raw_candidates = await self.generator.generate_plans(
            root_cause=cause,
            target_asset=target_asset,
            affected_systems=input_data.affected_systems,
            blast_radius=input_data.blast_radius,
        )

        # Step 2: Validate against allowed tool whitelist & enforce distinct strategies
        validated_plans = PlanValidator.validate_and_filter_plans(
            raw_plans=raw_candidates,
            target_asset=target_asset,
            blast_radius=input_data.blast_radius,
            correlation_id=input_data.correlation_id,
        )

        # Step 2.5: Filter out previously failed plans if replanning
        if input_data.excluded_plan_ids:
            remaining_plans = [p for p in validated_plans if p.plan_id not in input_data.excluded_plan_ids]
            if remaining_plans:
                validated_plans = remaining_plans

        # Step 2.8: Query Procedural Memory to bias toward proven historical strategies (>80% success & >=3 incidents)
        signature = f"{target_asset}:{cause[:30].strip().replace(' ', '_').upper()}"
        procedural_rec = None
        if self.procedural_memory:
            # Try specific signature, primary_failure_cause signature, and general target_asset signature
            procedural_rec = self.procedural_memory.get_best_known_strategy(signature)
            if not procedural_rec and input_data.primary_failure_cause:
                procedural_rec = self.procedural_memory.get_best_known_strategy(f"{target_asset}:{input_data.primary_failure_cause.upper()}")
            if not procedural_rec:
                procedural_rec = self.procedural_memory.get_best_known_strategy(target_asset)

        if procedural_rec:
            logger.info(
                f"Planner found qualifying procedural strategy for '{signature}': "
                f"'{procedural_rec.recommended_strategy}' ({procedural_rec.success_rate*100:.1f}% success). "
                f"Biasing plan selection."
            )
            boost_points = int(procedural_rec.confidence_boost * 100) if procedural_rec.confidence_boost <= 1.0 else int(procedural_rec.confidence_boost)
            for p in validated_plans:
                strat_name = getattr(p, "strategy", "").lower()
                action_tools = [a.tool.lower() for a in p.actions]
                rec_tool = procedural_rec.recommended_strategy.lower()

                if strat_name in rec_tool or rec_tool in strat_name or any(rec_tool in t for t in action_tools):
                    p.confidence = min(100, p.confidence + boost_points)

        # Step 3: Select primary recommended plan (highest confidence / lowest risk / procedural match)
        selected_plan = validated_plans[0]
        for p in validated_plans:
            strat_name = getattr(p, "strategy", "").lower()
            rec_tool = procedural_rec.recommended_strategy.lower() if procedural_rec else ""
            rec_match = bool(rec_tool and (strat_name in rec_tool or rec_tool in strat_name))
            curr_match = bool(rec_tool and (selected_plan.strategy.lower() in rec_tool or rec_tool in selected_plan.strategy.lower()))

            if (p.confidence > selected_plan.confidence) or (rec_match and not curr_match) or (p.confidence == selected_plan.confidence and p.risk_estimate == "LOW"):
                selected_plan = p

        # Step 4: Map actions to ActionStep for pipeline interoperability
        action_steps = [
            ActionStep(
                step_number=act.step,
                action_type=act.tool,
                target_asset=act.target_asset,
                parameters=act.parameters,
                rollback_command=selected_plan.rollback_method,
            )
            for act in selected_plan.actions
        ]

        return PlannerOutput(
            incident_id=input_data.incident_id,
            correlation_id=input_data.correlation_id,
            plan_id=selected_plan.plan_id,
            target_asset_id=target_asset,
            plans=validated_plans,
            selected_plan=selected_plan,
            action_steps=action_steps,
            estimated_recovery_time_sec=selected_plan.estimated_recovery_seconds,
            strategy_count=len(validated_plans),
            planned_at=datetime.now(timezone.utc).isoformat(),
        )
