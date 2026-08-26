"""
Prediction Engine Agent for AEGIS Ω.
Works alongside Sentinel to detect and mitigate impending incidents BEFORE hard thresholds are crossed.
Routes proactive PREDICTED_INCIDENT payloads through the SAME remediation pipeline:
Planner -> Counterfactual -> Risk -> Executor -> Verifier
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from runtime.event_bus import EventBus
from runtime.llm import get_gemini_client, GeminiClientWrapper
from memory import SemanticMemory, ProceduralMemory, semantic_memory, procedural_memory
from governance.guardrails import wrap_prompt_with_data_guardrails

from .forecaster import DeterministicTrendForecaster
from .models import (
    MetricReading,
    TrendForecast,
    PredictedIncident,
    PredictionInput,
    PredictionOutput,
)

logger = logging.getLogger(__name__)


class PredictionAgent(BaseAgent[PredictionInput, PredictionOutput]):
    """
    Prediction Agent:
    1. Deterministically detects growth rate and projected threshold breach via rolling linear regression.
    2. Uses Gemini (with guardrails) or deterministic filter to distinguish true saturation from transient jitter.
    3. Queries Semantic Memory for relevant cross-incident invariant patterns.
    4. Queries Procedural Memory for proven historical remediation strategies.
    5. Dispatches PREDICTED_INCIDENT to 'incident.root_cause' to invoke the standard remediation pipeline.
    """

    name = "Prediction"
    description = "Anticipates threshold crossings and initiates proactive remediation before failure."
    inbound_topic = "telemetry.metric"
    outbound_topic = "incident.root_cause"
    input_schema = PredictionInput
    output_schema = PredictionOutput

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        forecaster: Optional[DeterministicTrendForecaster] = None,
        sem_mem: Optional[SemanticMemory] = None,
        proc_mem: Optional[ProceduralMemory] = None,
        llm_wrapper: Optional[GeminiClientWrapper] = None,
    ):
        super().__init__(event_bus=event_bus)
        self.forecaster = forecaster or DeterministicTrendForecaster()
        self.semantic_memory = sem_mem or semantic_memory
        self.procedural_memory = proc_mem or procedural_memory
        self.llm_wrapper = llm_wrapper or get_gemini_client()

    async def _distinguish_incident_from_noise(
        self,
        forecast: TrendForecast,
    ) -> bool:
        """
        Use Gemini with guardrails to distinguish a sustained trajectory from transient jitter.
        Returns True if trend represents a genuine impending incident.
        """
        if not self.llm_wrapper.is_configured:
            # Deterministic heuristic: if slope is positive and projected breach <= horizon
            return forecast.is_breach_imminent and forecast.slope_per_sec > 0

        prompt, _ = wrap_prompt_with_data_guardrails(
            system_role=(
                "You are the AEGIS Ω Telemetry Noise Filter AI.\n"
                "Analyze the following projected metric trajectory and determine if it represents "
                "a true impending saturation incident or transient metric noise.\n"
                "Respond with strictly JSON: {\"is_real_incident\": true, \"confidence\": 0.92, \"rationale\": \"...\"}"
            ),
            untrusted_content=(
                f"Asset: {forecast.asset_id}\n"
                f"Metric: {forecast.metric_name}\n"
                f"Current Value: {forecast.current_value}\n"
                f"Threshold: {forecast.hard_threshold}\n"
                f"Rate of Change: {forecast.slope_per_sec}/sec\n"
                f"Projected Seconds to Breach: {forecast.projected_seconds_to_breach}s"
            ),
            agent_scope="PredictionNoiseFilter",
        )

        try:
            client = self.llm_wrapper.get_client()
            response = await client.aio.models.generate_content(
                model=self.llm_wrapper.model_name,
                contents=prompt,
            )
            raw = response.text.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            parsed = json.loads(raw)
            return bool(parsed.get("is_real_incident", True))
        except Exception as e:
            logger.warning(f"Noise filter LLM call failed: {e}. Defaulting to deterministic check.")
            return forecast.is_breach_imminent

    async def process(self, input_data: PredictionInput) -> Optional[PredictionOutput]:
        """
        Process a metric reading:
        - Updates rolling window
        - Evaluates trend forecast
        - If breach is imminent, generates PREDICTED_INCIDENT and returns PredictionOutput
        """
        forecast = self.forecaster.add_reading(
            asset_id=input_data.asset_id,
            metric_name=input_data.metric_name,
            value=input_data.value,
            timestamp=input_data.timestamp,
            threshold_override=input_data.threshold,
        )

        if not forecast or not forecast.is_breach_imminent:
            return None

        # Step 2: Distinguish incident from noise
        is_real = await self._distinguish_incident_from_noise(forecast)
        if not is_real:
            return None

        corr_id = input_data.correlation_id or f"corr-pred-{int(datetime.now().timestamp())}"
        inc_id = f"INC-PREDICTED-{input_data.asset_id}-{int(datetime.now().timestamp())}"
        signature = f"{input_data.asset_id}:{input_data.metric_name.upper()}_SATURATION"

        # Step 3: Query Semantic Memory for cross-incident pattern insights
        semantic_patterns = self.semantic_memory.search_patterns(input_data.metric_name)
        pattern_stmt = semantic_patterns[0].pattern_statement if semantic_patterns else None

        # Step 4: Query Procedural Memory for best-known historical strategy
        procedural_rec = self.procedural_memory.get_best_known_strategy(signature)
        if not procedural_rec:
            procedural_rec = self.procedural_memory.get_best_known_strategy(input_data.asset_id)

        rec_strategy = procedural_rec.recommended_strategy if procedural_rec else None

        root_cause_text = (
            f"PREDICTED_INCIDENT: Imminent breach on {input_data.asset_id} {input_data.metric_name} "
            f"(Current: {forecast.current_value}, Threshold: {forecast.hard_threshold}). "
            f"Projected crossing in {forecast.projected_seconds_to_breach}s at rate +{forecast.slope_per_sec}/s."
        )

        predicted_obj = PredictedIncident(
            incident_id=inc_id,
            correlation_id=corr_id,
            asset_id=input_data.asset_id,
            metric_name=input_data.metric_name,
            current_value=forecast.current_value,
            hard_threshold=forecast.hard_threshold,
            projected_seconds_to_breach=forecast.projected_seconds_to_breach,
            status="PREDICTED_INCIDENT",
            root_cause_prediction=root_cause_text,
            confidence=0.92 if procedural_rec else 0.85,
            historical_pattern=pattern_stmt,
            recommended_strategy=rec_strategy,
            predicted_at=datetime.now(timezone.utc).isoformat(),
        )

        output = PredictionOutput(
            incident_id=inc_id,
            correlation_id=corr_id,
            root_asset_id=input_data.asset_id,
            root_cause=root_cause_text,
            primary_failure_cause=f"{input_data.metric_name.upper()}_SATURATION",
            affected_systems=[input_data.asset_id],
            confidence_score=0.92 if procedural_rec else 0.85,
            status="PREDICTED_INCIDENT",
            forecast=forecast,
            blast_radius={"affected_count": 1, "assets": [input_data.asset_id]},
            predicted_incident=predicted_obj,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(
            f"PREDICTION ENGINE ALERT: Fired PREDICTED_INCIDENT on '{input_data.asset_id}' "
            f"for '{input_data.metric_name}'. Projected breach in {forecast.projected_seconds_to_breach}s."
        )
        return output
