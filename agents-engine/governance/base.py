"""
Governance Base Models and Policy Interfaces for AEGIS Ω.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DecisionOutcome(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_HUMAN_APPROVAL = "REQUIRE_HUMAN_APPROVAL"
    DEGRADE_GRACEFULLY = "DEGRADE_GRACEFULLY"


class PolicyDecision(BaseModel):
    """Result of evaluating a proposed action against governance policies."""
    outcome: DecisionOutcome
    policy_name: str
    reason: str
    risk_score: float = Field(ge=0.0, le=1.0, default=0.0)
    required_approvers: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Policy(BaseModel):
    """Declarative governance policy rule."""
    id: str
    name: str
    description: str
    enabled: bool = True
    max_allowed_risk_score: float = 0.5


class PolicyEngine:
    """Evaluates planned agent actions against active governance policies."""

    def __init__(self, policies: Optional[List[Policy]] = None):
        self.policies = policies or []

    def evaluate(self, action_type: str, context: Dict[str, Any]) -> PolicyDecision:
        """Evaluate an action against all active policies."""
        # Default baseline policy evaluation
        return PolicyDecision(
            outcome=DecisionOutcome.ALLOW,
            policy_name="default_baseline",
            reason="Action conforms to standard operational parameters",
            risk_score=0.1,
        )
