"""
Verifier Models and Schemas for AEGIS Ω.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Post-remediation verification status."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class VerifierOutput(BaseModel):
    """
    Required schema for Verifier Agent:
    { status, metric, before, after, expected_result, evidence }
    """
    incident_id: str
    correlation_id: str
    plan_id: str
    status: str = Field(
        description="Verification outcome: SUCCESS or FAILED",
    )
    metric: str = Field(
        description="Name of the exact original metric being verified",
    )
    before: float = Field(
        description="Value of the metric before remediation",
    )
    after: float = Field(
        description="Value of the metric after remediation",
    )
    expected_result: str = Field(
        description="Expected SLA target boundary (e.g. latency_ms <= 200.0)",
    )
    evidence: str = Field(
        description="Deterministic mathematical explanation of the before/after comparison",
    )
    health_status: str = Field(
        default="HEALTHY",
        description="Overall assessed service health: HEALTHY or DEGRADED",
    )
    metrics_normalized: bool = Field(
        default=True,
        description="True if metrics returned to normal baseline",
    )
    verification_passed: bool = Field(
        default=True,
        description="True if verification passed successfully",
    )
    verified_at: str
