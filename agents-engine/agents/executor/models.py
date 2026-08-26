"""
Executor Models and Schemas for AEGIS Ω.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .audit import AuditRecord


class ExecutorOutput(BaseModel):
    """
    Output payload from Executor Agent detailing actuation status and audit logs.
    """
    incident_id: str
    correlation_id: str
    plan_id: str
    execution_status: str = Field(
        description="Actuation status: SUCCESS, SUCCESS_REVIEW_FLAGGED, HELD_FOR_APPROVAL, REFUSED_CRITICAL_RISK, BLOCKED_BY_GATE, FAILED_VALIDATION, FAILED",
    )
    actions_executed: List[str] = Field(
        default_factory=list,
        description="Descriptions of all successfully dispatched actions",
    )
    audit_records: List[AuditRecord] = Field(
        default_factory=list,
        description="Audit records generated during execution attempt",
    )
    actuator_response_code: int = Field(
        description="HTTP-style response code: 200 (executed), 403 (blocked/refused), 400 (bad params), 500 (error)",
    )
    executed_at: str
