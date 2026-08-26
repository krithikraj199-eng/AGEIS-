"""
Recovery Models and Replanning Schemas for AEGIS Ω.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RecoveryAttempt(BaseModel):
    """
    Schema for tracking each remediation/rollback attempt:
    { attempt_number, plan_id, outcome, timestamp }
    """
    attempt_number: int = Field(
        description="Sequential attempt count (1 to 3)",
    )
    plan_id: str = Field(
        description="ID of the plan executed in this attempt",
    )
    outcome: str = Field(
        description="Attempt outcome: SUCCESS, FAILED, ROLLED_BACK, ESCALATED",
    )
    timestamp: str = Field(
        description="ISO 8601 UTC timestamp of attempt execution",
    )
    rollback_executed: bool = Field(
        default=False,
        description="True if rollback method was actuated following failure",
    )
    rollback_details: Optional[str] = Field(
        default=None,
        description="Summary of the rollback action executed",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if attempt failed",
    )


class RecoveryOutput(BaseModel):
    """
    Output payload from Recovery Agent detailing final incident resolution or escalation.
    """
    correlation_id: str
    incident_id: str
    plan_id: str
    final_status: str = Field(
        description="Final resolution status: RESOLVED or ESCALATION_REQUIRED",
    )
    rollback_required: bool = Field(
        default=False,
        description="True if rollback was performed during recovery",
    )
    attempts: List[RecoveryAttempt] = Field(
        default_factory=list,
        description="Chronological log of all remediation and rollback attempts",
    )
    total_attempts: int = Field(
        default=1,
        description="Total number of attempts executed before resolution/escalation",
    )
    resolution_summary: str = Field(
        description="Comprehensive summary of resolution or escalation reasons",
    )
    resolved_at: str
