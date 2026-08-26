"""
Risk Scoring Models and Gate Decision Schemas for AEGIS Ω Risk Engine.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RiskTier(str, Enum):
    """Governance risk tiers."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GateDecision(str, Enum):
    """Execution gate enforcement decisions."""
    AUTO_EXECUTE = "AUTO_EXECUTE"
    SUPERVISOR_REVIEW = "SUPERVISOR_REVIEW"
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    BLOCKED = "BLOCKED"


class RiskOutput(BaseModel):
    """
    Required output schema for Risk Engine:
    { risk_score, tier, gate_decision, rationale }
    """
    incident_id: str
    correlation_id: str
    plan_id: str
    risk_score: int = Field(
        ge=0,
        le=100,
        description="Calculated deterministic risk score (0 to 100)",
    )
    tier: str = Field(
        description="Assessed risk tier: LOW, MEDIUM, HIGH, CRITICAL",
    )
    gate_decision: str = Field(
        description="Gate decision: AUTO_EXECUTE, SUPERVISOR_REVIEW, HUMAN_APPROVAL_REQUIRED, BLOCKED",
    )
    rationale: str = Field(
        description="Detailed mathematical explanation of the risk score and gate decision",
    )
    is_approved: bool = Field(
        description="True if permitted for automated or supervisor-flagged execution",
    )
    requires_human_approval: bool = Field(
        description="True if high-risk plan requires explicit human sign-off",
    )
    policy_decision: str = "PERMIT"
    evaluated_at: str
    selected_plan: Optional[Any] = None
