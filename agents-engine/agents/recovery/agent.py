"""
Recovery Agent for AEGIS Ω.
Rollback & Replanning Engine: Manages incident lifecycle resolution, automated rollback upon verification failure,
bounded 3-attempt replanning loops, and escalation controls.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from runtime.event_bus import EventBus
from observability.telemetry import trace_span
from tools.registry import ToolRegistry

from .models import RecoveryAttempt, RecoveryOutput

logger = logging.getLogger(__name__)


class RecoveryInput(BaseModel):
    """Input payload for Recovery Agent from Verifier."""
    correlation_id: str
    incident_id: str
    plan_id: str = "PLAN-DEFAULT"
    health_status: str = "HEALTHY"
    metrics_normalized: bool = True
    verification_passed: bool = True
    verified_at: Optional[str] = None
    status: Optional[str] = None
    metric: Optional[str] = None
    before: Optional[float] = None
    after: Optional[float] = None
    expected_result: Optional[str] = None
    evidence: Optional[str] = None
    target_asset: Optional[str] = "DATABASE-01"
    rollback_method: Optional[str] = None
    root_cause_context: Optional[Dict[str, Any]] = None


class RecoveryAgent(BaseAgent[RecoveryInput, RecoveryOutput]):
    """
    Recovery Agent:
    - On verification SUCCESS: Marks incident RESOLVED and closes lifecycle.
    - On verification FAILED:
        1. Executes failed plan's rollback_method.
        2. Records rollback attempt in immutable history.
        3. Excludes failed plan_id.
        4. Reinvokes Planner -> Counterfactual -> Risk -> Executor -> Verifier.
        5. Enforces MAX_ATTEMPTS = 3 (escalates with ESCALATION_REQUIRED if exhausted).
    - Prevents infinite loops.
    """

    name = "Recovery"
    description = "Manages post-verification rollback, replanning orchestration, and incident lifecycle closure."
    inbound_topic = "incident.verified"
    outbound_topic = "incident.resolved"
    input_schema = RecoveryInput
    output_schema = RecoveryOutput

    MAX_ATTEMPTS: int = 3

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        super().__init__(event_bus=event_bus)
        self.registry = registry or ToolRegistry()
        # Track attempt history per incident_id
        self._incident_attempts: Dict[str, List[RecoveryAttempt]] = {}
        self._excluded_plans: Dict[str, List[str]] = {}

    def start(self) -> None:
        """Subscribe to both normal verification success and verification failure topics."""
        super().start()
        if self.event_bus:
            self.event_bus.subscribe("incident.verification_failed", self.handle_verification_failed)

    async def handle_verification_failed(self, event_data: Any) -> None:
        """Handler for verification failure events."""
        if isinstance(event_data, dict):
            input_data = self.input_schema.model_validate(event_data)
        elif isinstance(event_data, BaseModel):
            input_data = self.input_schema.model_validate(event_data.model_dump())
        else:
            return

        input_data.verification_passed = False
        await self.process(input_data)

    async def _execute_rollback(
        self,
        target_asset: str,
        rollback_method: Optional[str],
    ) -> tuple[bool, str]:
        """Execute rollback action through ToolRegistry."""
        method_str = rollback_method or "restart_service"
        target = target_asset or "DATABASE-01"

        if "restart" in method_str.lower():
            res = await self.registry.execute_tool("restart_service", {"asset_id": target, "grace_period_sec": 5})
        elif "restore" in method_str.lower() or "config" in method_str.lower():
            res = await self.registry.execute_tool(
                "restore_configuration",
                {"asset_id": target, "config_snapshot_id": "snap-baseline-001"},
            )
        elif "scale" in method_str.lower():
            res = await self.registry.execute_tool("scale_service", {"asset_id": target, "factor": 1.0, "replicas": 2})
        else:
            res = await self.registry.execute_tool("restart_service", {"asset_id": target, "grace_period_sec": 5})

        return res.success, res.result.get("message", f"Rolled back {target} via {method_str}")

    async def process(self, input_data: RecoveryInput) -> RecoveryOutput:
        """
        Process verification result: either finalize resolution or execute rollback & replanning.
        """
        incident_id = input_data.incident_id or "INC-DEFAULT"
        plan_id = input_data.plan_id or "PLAN-DEFAULT"
        target_asset = input_data.target_asset or "DATABASE-01"
        now_ts = datetime.now(timezone.utc).isoformat()

        # Initialize attempt history tracking
        if incident_id not in self._incident_attempts:
            self._incident_attempts[incident_id] = []
        if incident_id not in self._excluded_plans:
            self._excluded_plans[incident_id] = []

        history = self._incident_attempts[incident_id]
        excluded = self._excluded_plans[incident_id]
        current_attempt = len(history) + 1

        is_success = bool(
            input_data.verification_passed
            and (input_data.status is None or input_data.status.upper() == "SUCCESS")
        )

        # ---------------------------------------------------------
        # Case A: Verification SUCCEEDED
        # ---------------------------------------------------------
        if is_success:
            attempt_rec = RecoveryAttempt(
                attempt_number=current_attempt,
                plan_id=plan_id,
                outcome="SUCCESS",
                timestamp=now_ts,
                rollback_executed=False,
            )
            history.append(attempt_rec)

            summary = (
                f"Incident {incident_id} successfully mitigated via plan {plan_id} on attempt {current_attempt}. "
                f"Telemetry normalized."
            )
            logger.info(summary)

            return RecoveryOutput(
                correlation_id=input_data.correlation_id,
                incident_id=incident_id,
                plan_id=plan_id,
                final_status="RESOLVED",
                rollback_required=False,
                attempts=list(history),
                total_attempts=len(history),
                resolution_summary=summary,
                resolved_at=now_ts,
            )

        # ---------------------------------------------------------
        # Case B: Verification FAILED -> Execute Rollback & Replan
        # ---------------------------------------------------------
        logger.warning(
            f"Verification FAILED for incident {incident_id} (Attempt {current_attempt}/{self.MAX_ATTEMPTS}). "
            f"Executing rollback for plan {plan_id}."
        )

        # Step 3: Execute rollback method
        rb_success, rb_details = await self._execute_rollback(
            target_asset=target_asset,
            rollback_method=input_data.rollback_method,
        )

        # Step 4: Record rollback attempt in immutable history
        attempt_rec = RecoveryAttempt(
            attempt_number=current_attempt,
            plan_id=plan_id,
            outcome="FAILED",
            timestamp=now_ts,
            rollback_executed=rb_success,
            rollback_details=rb_details,
            error_message=input_data.evidence or "Verification failed to meet SLA thresholds",
        )
        history.append(attempt_rec)

        # Step 6: Exclude failed plan ID
        if plan_id not in excluded:
            excluded.append(plan_id)

        # Step 7: Check attempt exhaustion limit
        if current_attempt >= self.MAX_ATTEMPTS:
            escalation_summary = (
                f"All {self.MAX_ATTEMPTS} automated remediation attempts failed for incident {incident_id}. "
                f"Excluded plans: {excluded}. Halting automated loop. ESCALATION_REQUIRED for SRE on-call."
            )
            logger.error(escalation_summary)

            output = RecoveryOutput(
                correlation_id=input_data.correlation_id,
                incident_id=incident_id,
                plan_id=plan_id,
                final_status="ESCALATION_REQUIRED",
                rollback_required=True,
                attempts=list(history),
                total_attempts=len(history),
                resolution_summary=escalation_summary,
                resolved_at=now_ts,
            )

            if self.event_bus:
                await self.event_bus.publish("incident.escalated", output)
                await self.event_bus.publish("incident.resolved", output)

            return output

        # Step 5: Reinvoke Planner with excluded plan IDs
        replan_summary = (
            f"Attempt {current_attempt} failed with plan {plan_id}. Rollback executed. "
            f"Triggering replanning with excluded plans: {excluded}."
        )
        logger.info(replan_summary)

        # Step 5: Prepare output snapshot before replanning
        output_snapshot = RecoveryOutput(
            correlation_id=input_data.correlation_id,
            incident_id=incident_id,
            plan_id=plan_id,
            final_status="ROLLED_BACK",
            rollback_required=True,
            attempts=list(history),
            total_attempts=current_attempt,
            resolution_summary=replan_summary,
            resolved_at=now_ts,
        )

        if self.event_bus:
            replan_payload = {
                "correlation_id": input_data.correlation_id,
                "incident_id": incident_id,
                "root_asset_id": target_asset,
                "root_cause": input_data.evidence or f"Verification failed on {target_asset}",
                "affected_systems": [target_asset],
                "excluded_plan_ids": list(excluded),
                "confidence_score": 0.85,
                "diagnosed_at": now_ts,
            }
            # Publish to incident.root_cause so Planner -> Counterfactual -> Risk -> Executor -> Verifier re-runs
            await self.event_bus.publish("incident.root_cause", replan_payload)

        return output_snapshot
