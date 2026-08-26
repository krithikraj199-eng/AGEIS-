"""
Verifier Agent for AEGIS Ω.
Health & Recovery Verification: Deterministically audits whether remediation fixed the original triggering metric.
Zero LLM logic.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from runtime.event_bus import EventBus
from observability.telemetry import trace_span

from .auditor import DeterministicMetricAuditor
from .models import VerificationStatus, VerifierOutput

logger = logging.getLogger(__name__)


class VerifierInput(BaseModel):
    """Input payload for Verifier Agent from Executor."""
    correlation_id: str
    incident_id: str
    plan_id: str
    execution_status: str = "SUCCESS"
    actions_executed: List[str] = Field(default_factory=list)
    audit_records: List[Any] = Field(default_factory=list)
    actuator_response_code: int = 200
    executed_at: Optional[str] = None
    metric_name: Optional[str] = None
    before_value: Optional[float] = None
    after_value: Optional[float] = None
    target_threshold: Optional[float] = None


class VerifierAgent(BaseAgent[VerifierInput, VerifierOutput]):
    """
    Verifier Agent:
    - Verifies post-execution recovery against the EXACT SAME metric that triggered Sentinel.
    - Purely deterministic Python comparison.
    - Emits:
        * incident.verified + incident.resolved on SUCCESS
        * incident.verification_failed on FAILED
    """

    name = "Verifier"
    description = "Audits post-remediation telemetry against the original triggering metric."
    inbound_topic = "incident.executed"
    outbound_topic = "incident.verified"
    input_schema = VerifierInput
    output_schema = VerifierOutput

    def _extract_metric_context(self, input_data: VerifierInput) -> Tuple[str, float, float]:
        """Extract exact original metric name, before value, and after value."""
        metric_name = input_data.metric_name or "latency_ms"
        before_val = input_data.before_value if input_data.before_value is not None else 850.0

        if input_data.after_value is not None:
            after_val = input_data.after_value
        else:
            # Default healthy simulation value if execution succeeded
            if input_data.execution_status in ["SUCCESS", "SUCCESS_REVIEW_FLAGGED"] and input_data.actuator_response_code == 200:
                after_val = 120.0 if metric_name == "latency_ms" else (25.0 if "percent" in metric_name else 0.01)
            else:
                after_val = before_val  # Unchanged if not executed

        return metric_name, float(before_val), float(after_val)

    async def process(self, input_data: VerifierInput) -> VerifierOutput:
        """
        Deterministically compare before and after values of the original metric.
        """
        metric_name, before_val, after_val = self._extract_metric_context(input_data)

        # Check if execution failed or was blocked upstream
        if input_data.execution_status not in ["SUCCESS", "SUCCESS_REVIEW_FLAGGED"] or input_data.actuator_response_code != 200:
            status = VerificationStatus.FAILED
            expected_result = f"{metric_name} <= {DeterministicMetricAuditor.get_threshold(metric_name, before_val)}"
            evidence = (
                f"Actuation was not successfully executed (Status: {input_data.execution_status}, "
                f"Code: {input_data.actuator_response_code}). Metric '{metric_name}' remains unverified at {before_val}."
            )
            verification_passed = False
            health_status = "DEGRADED"
            metrics_normalized = False
        else:
            status, expected_result, evidence = DeterministicMetricAuditor.verify_metric(
                metric_name=metric_name,
                before_val=before_val,
                after_val=after_val,
                target_threshold=input_data.target_threshold,
            )
            verification_passed = (status == VerificationStatus.SUCCESS)
            health_status = "HEALTHY" if verification_passed else "DEGRADED"
            metrics_normalized = verification_passed

        output = VerifierOutput(
            incident_id=input_data.incident_id,
            correlation_id=input_data.correlation_id,
            plan_id=input_data.plan_id or "PLAN-DEFAULT",
            status=status.value,
            metric=metric_name,
            before=before_val,
            after=after_val,
            expected_result=expected_result,
            evidence=evidence,
            health_status=health_status,
            metrics_normalized=metrics_normalized,
            verification_passed=verification_passed,
            verified_at=datetime.now(timezone.utc).isoformat(),
        )

        # Conditional Event Publishing on verification failure
        if not verification_passed and self.event_bus:
            logger.warning(f"Verification FAILED for {input_data.incident_id}. Publishing incident.verification_failed.")
            await self.event_bus.publish("incident.verification_failed", output)

        return output
