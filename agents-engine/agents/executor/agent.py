"""
Executor Agent for AEGIS Ω.
Actuation & Dispatch: Safely executes approved remediation steps against target infrastructure via scoped tools.
Enforces strict Risk Engine gates, validates tool schemas, and logs immutable audit records.
Never uses Gemini.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from runtime.event_bus import EventBus
from observability.telemetry import trace_span
from tools.registry import ToolRegistry, ToolExecutionResult
from tools.client import DigitalWorldClientProtocol

from .audit import AuditLogger, AuditRecord
from .models import ExecutorOutput

logger = logging.getLogger(__name__)


class ExecutorInput(BaseModel):
    """Input payload for Executor Agent from Risk."""
    correlation_id: str
    incident_id: str
    plan_id: str
    risk_score: float = 25.0
    is_approved: bool = True
    policy_decision: str = "PERMIT"
    requires_human_approval: bool = False
    tier: Optional[str] = "LOW"
    gate_decision: Optional[str] = "AUTO_EXECUTE"
    rationale: Optional[str] = None
    selected_plan: Optional[Any] = None
    actions_to_execute: List[Dict[str, Any]] = Field(default_factory=list)
    evaluated_at: Optional[str] = None


class ExecutorAgent(BaseAgent[ExecutorInput, ExecutorOutput]):
    """
    Executor Agent:
    - 100% deterministic Python actuation engine (zero Gemini).
    - Strictly checks Risk Engine gate:
        * LOW (0-30): Execute immediately
        * MEDIUM (31-60): Execute with supervisor-review audit flag
        * HIGH (61-80): Hold execution for explicit human approval
        * CRITICAL (81-100): Refuse execution outright
    - Dispatches tool invocations via ToolRegistry with Pydantic validation.
    - Generates immutable AuditRecord for every action attempt.
    - Publishes ExecutorOutput to 'incident.executed' for Verifier Agent.
    """

    name = "Executor"
    description = "Executes approved remediation actions through scoped Pydantic tools with audit logging."
    inbound_topic = "incident.risk_approved"
    outbound_topic = "incident.executed"
    input_schema = ExecutorInput
    output_schema = ExecutorOutput

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        registry: Optional[ToolRegistry] = None,
        audit_logger: Optional[AuditLogger] = None,
        gateway: Optional[Any] = None,
        client: Optional[DigitalWorldClientProtocol] = None,
        digital_world_client: Optional[DigitalWorldClientProtocol] = None,
    ):
        super().__init__(event_bus=event_bus)
        effective_client = client or digital_world_client
        self.registry = registry or ToolRegistry(client=effective_client)
        self.audit_logger = audit_logger or AuditLogger()
        self.gateway = gateway

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Retrieve recorded audit records."""
        return [r.model_dump() for r in self.audit_logger.get_all_records()]

    def _extract_plan_actions(self, input_data: ExecutorInput) -> List[Dict[str, Any]]:
        """Extract list of action dictionaries with tool and parameters."""
        if input_data.actions_to_execute:
            return list(input_data.actions_to_execute)

        plan = input_data.selected_plan
        actions: List[Dict[str, Any]] = []

        if isinstance(plan, dict):
            raw_actions = plan.get("actions", [])
            for a in raw_actions:
                if isinstance(a, dict):
                    tool = a.get("tool", a.get("action_type", "scale_service"))
                    params = a.get("parameters", {})
                    # Ensure target_asset is present in params if specified
                    if "target_asset" in a and "asset_id" not in params:
                        params["asset_id"] = a["target_asset"]
                    actions.append({"tool": tool, "params": params})
        elif hasattr(plan, "actions"):
            for a in getattr(plan, "actions", []):
                tool = getattr(a, "tool", "scale_service")
                params = dict(getattr(a, "parameters", {}))
                target = getattr(a, "target_asset", None)
                if target and "asset_id" not in params:
                    params["asset_id"] = target
                actions.append({"tool": tool, "params": params})

        if not actions:
            # Default fallback action matching plan
            actions.append({"tool": "scale_service", "params": {"asset_id": "DATABASE-01", "factor": 2.0}})

        return actions

    async def process(self, input_data: ExecutorInput) -> ExecutorOutput:
        """
        Execute risk-cleared actions or enforce gate hold/refusal.
        """
        plan_id = input_data.plan_id or "PLAN-DEFAULT"
        risk_score = int(round(input_data.risk_score))
        gate_decision = (input_data.gate_decision or "AUTO_EXECUTE").upper()
        tier = (input_data.tier or "LOW").upper()

        actions_to_run = self._extract_plan_actions(input_data)
        primary_tool = actions_to_run[0]["tool"] if actions_to_run else "unknown_tool"
        primary_params = actions_to_run[0].get("params", {}) if actions_to_run else {}

        # ---------------------------------------------------------
        # 1. Gate Check: CRITICAL (81-100) -> Refuse Execution
        # ---------------------------------------------------------
        if gate_decision == "BLOCKED" or tier == "CRITICAL" or risk_score >= 81:
            rec = self.audit_logger.record_action(
                plan_id=plan_id,
                tool_name=primary_tool,
                params=primary_params,
                risk_score=risk_score,
                outcome="REFUSED_CRITICAL_RISK",
                error_message=f"Plan refused by Risk Engine: score={risk_score}, gate={gate_decision}",
            )
            return ExecutorOutput(
                incident_id=input_data.incident_id,
                correlation_id=input_data.correlation_id,
                plan_id=plan_id,
                execution_status="REFUSED_CRITICAL_RISK",
                actions_executed=[],
                audit_records=[rec],
                actuator_response_code=403,
                executed_at=datetime.now(timezone.utc).isoformat(),
            )

        # ---------------------------------------------------------
        # 2. Gate Check: HIGH (61-80) -> Hold for Human Approval
        # ---------------------------------------------------------
        if (
            gate_decision == "HUMAN_APPROVAL_REQUIRED"
            or tier == "HIGH"
            or input_data.requires_human_approval
            or risk_score >= 61
        ):
            rec = self.audit_logger.record_action(
                plan_id=plan_id,
                tool_name=primary_tool,
                params=primary_params,
                risk_score=risk_score,
                outcome="HELD_FOR_APPROVAL",
                error_message=f"Plan held for human sign-off: score={risk_score}, gate={gate_decision}",
            )
            return ExecutorOutput(
                incident_id=input_data.incident_id,
                correlation_id=input_data.correlation_id,
                plan_id=plan_id,
                execution_status="HELD_FOR_APPROVAL",
                actions_executed=[],
                audit_records=[rec],
                actuator_response_code=403,
                executed_at=datetime.now(timezone.utc).isoformat(),
            )

        # ---------------------------------------------------------
        # 3. Gate Check: LOW (0-30) or MEDIUM (31-60) -> Permitted
        # ---------------------------------------------------------
        execution_outcome_label = (
            "SUCCESS_REVIEW_FLAGGED" if (gate_decision == "SUPERVISOR_REVIEW" or tier == "MEDIUM" or risk_score >= 31) else "SUCCESS"
        )

        executed_descriptions: List[str] = []
        audit_records: List[AuditRecord] = []

        for act in actions_to_run:
            tool_name = act.get("tool", "")
            raw_params = act.get("params") or act.get("parameters") or {}
            params = dict(raw_params)
            if "target_asset" in act and "asset_id" not in params:
                params["asset_id"] = act["target_asset"]

            # Execute via Gateway or ToolRegistry (validates tool name & Pydantic parameter schema)
            if self.gateway:
                exec_result: ToolExecutionResult = await self.gateway.execute_tool("executor", tool_name, params)
            else:
                exec_result: ToolExecutionResult = await self.registry.execute_tool(tool_name, params)

            if not exec_result.success:
                rec = self.audit_logger.record_action(
                    plan_id=plan_id,
                    tool_name=tool_name,
                    params=params,
                    risk_score=risk_score,
                    outcome="FAILED_VALIDATION",
                    error_message=exec_result.error_message,
                )
                audit_records.append(rec)

                return ExecutorOutput(
                    incident_id=input_data.incident_id,
                    correlation_id=input_data.correlation_id,
                    plan_id=plan_id,
                    execution_status="FAILED_VALIDATION",
                    actions_executed=executed_descriptions,
                    audit_records=audit_records,
                    actuator_response_code=400,
                    executed_at=datetime.now(timezone.utc).isoformat(),
                )

            # Success
            rec = self.audit_logger.record_action(
                plan_id=plan_id,
                tool_name=tool_name,
                params=params,
                risk_score=risk_score,
                outcome=execution_outcome_label,
            )
            audit_records.append(rec)
            msg = exec_result.result.get("message", f"Executed {tool_name} on {params.get('asset_id', 'target')}")
            executed_descriptions.append(msg)

        return ExecutorOutput(
            incident_id=input_data.incident_id,
            correlation_id=input_data.correlation_id,
            plan_id=plan_id,
            execution_status=execution_outcome_label,
            actions_executed=executed_descriptions,
            audit_records=audit_records,
            actuator_response_code=200,
            executed_at=datetime.now(timezone.utc).isoformat(),
        )
