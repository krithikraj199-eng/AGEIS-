"""
Remediation Plan Models and Tool Whitelist for AEGIS Ω Planner Agent.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, Field, field_validator


class AllowedTool(str, Enum):
    """Strictly allowed remediation tools."""
    RESTART_SERVICE = "restart_service"
    SCALE_SERVICE = "scale_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    CLEAR_CACHE = "clear_cache"
    QUARANTINE_ASSET = "quarantine_asset"
    RESTORE_CONFIGURATION = "restore_configuration"


ALLOWED_TOOL_NAMES: Set[str] = {t.value for t in AllowedTool}


class RemediationAction(BaseModel):
    """An individual atomic remediation action using an allowed tool."""
    step: int
    tool: str = Field(
        description="Must strictly be one of the allowed tool names",
    )
    target_asset: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("tool")
    @classmethod
    def validate_allowed_tool(cls, v: str) -> str:
        if v not in ALLOWED_TOOL_NAMES:
            raise ValueError(
                f"Disallowed tool '{v}'. Allowed tools: {sorted(list(ALLOWED_TOOL_NAMES))}"
            )
        return v


class ActionStep(BaseModel):
    """Compatibility representation for action steps."""
    step_number: int
    action_type: str
    target_asset: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    rollback_command: str


class RemediationPlan(BaseModel):
    """
    Required schema for a remediation plan:
    {
        plan_id, name, actions, expected_result,
        estimated_recovery_seconds, risk_estimate, downtime_estimate,
        blast_radius, confidence, rollback_method
    }
    """
    plan_id: str
    name: str
    strategy: str = Field(
        description="Strategy category: restart, scale, rollback, clear_cache, quarantine, restore_configuration",
    )
    actions: List[RemediationAction] = Field(
        description="Ordered list of atomic remediation actions using whitelisted tools",
    )
    expected_result: str
    estimated_recovery_seconds: int = Field(ge=1)
    risk_estimate: str = Field(
        description="Risk level: LOW, MEDIUM, HIGH, CRITICAL",
    )
    downtime_estimate: str
    blast_radius: Union[Dict[str, Any], str, Any]
    confidence: int = Field(ge=0, le=100)
    rollback_method: str = Field(
        min_length=5,
        description="Explicit instructions or procedure to rollback this plan if verification fails",
    )

    @field_validator("actions")
    @classmethod
    def validate_actions_not_empty(cls, v: List[RemediationAction]) -> List[RemediationAction]:
        if not v:
            raise ValueError("Remediation plan must contain at least one action step.")
        return v


class PlannerOutput(BaseModel):
    """
    Output payload from Planner Agent for Counterfactual and Risk agents.
    """
    incident_id: str
    correlation_id: str
    plan_id: str
    target_asset_id: str
    plans: List[RemediationPlan] = Field(
        description="2 to 4 distinct remediation plans",
    )
    selected_plan: RemediationPlan
    action_steps: List[ActionStep] = Field(
        default_factory=list,
        description="Downstream pipeline compatibility action list",
    )
    estimated_recovery_time_sec: int
    strategy_count: int
    planned_at: str
