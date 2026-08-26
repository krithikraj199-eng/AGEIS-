"""
Audit Trail Logging for AEGIS Ω Executor Agent.
Ensures every execution, refusal, or block is immutably recorded for governance.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    """
    Required schema for execution audit record:
    { timestamp, plan_id, tool_name, params, actor, risk_score, outcome }
    """
    timestamp: str = Field(
        description="ISO 8601 UTC timestamp of execution attempt",
    )
    plan_id: str = Field(
        description="ID of the remediation plan being executed",
    )
    tool_name: str = Field(
        description="Name of the invoked remediation tool",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters passed to the tool invocation",
    )
    actor: str = Field(
        default="AEGIS_OMEGA_EXECUTOR",
        description="Entity or agent responsible for the actuation attempt",
    )
    risk_score: int = Field(
        description="Assessed risk score (0-100) at time of execution",
    )
    outcome: str = Field(
        description="Actuation outcome: SUCCESS, FAILED, REFUSED, BLOCKED, HELD",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if execution was refused or failed",
    )


class AuditLogger:
    """In-memory and persistent audit logger for remediation actions."""

    def __init__(self):
        self._records: List[AuditRecord] = []

    def record_action(
        self,
        plan_id: str,
        tool_name: str,
        params: Dict[str, Any],
        risk_score: int,
        outcome: str,
        actor: str = "AEGIS_OMEGA_EXECUTOR",
        error_message: Optional[str] = None,
    ) -> AuditRecord:
        """Create and store an immutable audit record."""
        rec = AuditRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            plan_id=plan_id,
            tool_name=tool_name,
            params=dict(params),
            actor=actor,
            risk_score=risk_score,
            outcome=outcome,
            error_message=error_message,
        )
        self._records.append(rec)
        return rec

    def get_all_records(self) -> List[AuditRecord]:
        return list(self._records)
