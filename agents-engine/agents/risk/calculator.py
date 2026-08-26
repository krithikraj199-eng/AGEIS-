"""
Deterministic Risk Calculator and Gate Decision Engine for AEGIS Ω.
Computes 0-100 risk score and enforces strict 4-tier execution gates in pure Python.
"""

from typing import Any, Dict, List, Optional, Tuple
from .models import GateDecision, RiskTier


class DeterministicRiskCalculator:
    """
    Pure Python deterministic risk calculator.
    Gemini is strictly forbidden in this component.
    """

    # Initial base risk values per tool
    BASE_TOOL_RISKS: Dict[str, int] = {
        "clear_cache": 8,
        "restart_service": 22,
        "scale_service": 25,
        "rollback_deployment": 47,
        "restore_configuration": 50,
        "quarantine_asset": 61,
    }

    # Security event penalty
    SECURITY_EVENT_PENALTY: int = 25

    @classmethod
    def get_base_tool_risk(cls, tool_name: str) -> int:
        """Retrieve initial base risk for a tool."""
        return cls.BASE_TOOL_RISKS.get(tool_name.lower().strip(), 25)

    @classmethod
    def calculate_score(
        cls,
        tool_name: str,
        blast_radius_count: int = 1,
        is_security_event: bool = False,
        additional_penalty: int = 0,
    ) -> int:
        """
        Compute total risk score in [0, 100]:
        Total = Base Tool Risk + Blast Radius Adder + Security Event Penalty + Additional Adjustments
        """
        base_risk = cls.get_base_tool_risk(tool_name)

        # Blast radius adjustment: +3 points per additional affected service beyond the root (max +15)
        blast_adder = min(15, max(0, (blast_radius_count - 1) * 3))

        # Security penalty
        sec_penalty = cls.SECURITY_EVENT_PENALTY if is_security_event else 0

        total = base_risk + blast_adder + sec_penalty + additional_penalty
        return max(0, min(100, int(round(total))))

    @classmethod
    def evaluate_tier_and_gate(cls, score: int) -> Tuple[RiskTier, GateDecision, bool, bool]:
        """
        Map 0-100 score to RiskTier and GateDecision:
          - 0-30:   LOW      -> AUTO_EXECUTE
          - 31-60:  MEDIUM   -> SUPERVISOR_REVIEW
          - 61-80:  HIGH     -> HUMAN_APPROVAL_REQUIRED
          - 81-100: CRITICAL -> BLOCKED
        Returns (tier, gate_decision, is_approved, requires_human_approval).
        """
        clamped_score = max(0, min(100, score))

        if clamped_score <= 30:
            return (
                RiskTier.LOW,
                GateDecision.AUTO_EXECUTE,
                True,   # is_approved
                False,  # requires_human_approval
            )
        elif clamped_score <= 60:
            return (
                RiskTier.MEDIUM,
                GateDecision.SUPERVISOR_REVIEW,
                True,   # is_approved (flagged for review)
                False,
            )
        elif clamped_score <= 80:
            return (
                RiskTier.HIGH,
                GateDecision.HUMAN_APPROVAL_REQUIRED,
                False,  # is_approved (holds until human sign-off)
                True,
            )
        else:
            return (
                RiskTier.CRITICAL,
                GateDecision.BLOCKED,
                False,  # is_approved (blocked)
                False,
            )
