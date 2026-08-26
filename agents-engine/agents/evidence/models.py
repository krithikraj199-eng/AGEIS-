"""
Evidence Schema Models for AEGIS Ω.
Strictly maps claims to verified metric deltas and enforces anti-fabrication constraints.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class EvidenceItem(BaseModel):
    """
    Evidence item proving a specific operational metric delta.
    Every evidence item MUST map directly to an actual measured metric.
    """
    claim: str = Field(
        description="Factual claim describing the observed metric change",
    )
    metric: str = Field(
        description="Exact metric identifier backing this evidence item",
    )
    before: float = Field(
        description="Baseline or pre-incident metric value",
    )
    after: float = Field(
        description="Measured metric value during incident",
    )
    delta: str = Field(
        description="Calculated change percentage or delta string (e.g. '+317.0%')",
    )
    source: str = Field(
        default="telemetry_stream",
        description="Subsystem or sensor providing the metric data",
    )
    is_verified: bool = Field(
        default=True,
        description="True if backed by ground-truth telemetry metric",
    )


class EvidenceOutput(BaseModel):
    """
    Structured evidence package required for downstream resilience agents:
    { root_cause_candidate, evidence, historical_similarity, confidence }
    """
    incident_id: str
    correlation_id: str
    asset_id: str
    evidence_id: str
    root_cause_candidate: str
    evidence: List[EvidenceItem] = Field(
        description="List of rigorously verified evidence items mapped to actual metrics",
    )
    historical_similarity: float = Field(
        ge=0.0,
        le=1.0,
        description="Similarity score (0.0 to 1.0) against historical incident store",
    )
    confidence: int = Field(
        ge=0,
        le=100,
        description="Overall evidence confidence score (0 to 100)",
    )
    cryptographic_hash: str
    collected_at: str
    evidence_bundle: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("evidence")
    @classmethod
    def validate_no_empty_or_fabricated_evidence(cls, v: List[EvidenceItem]) -> List[EvidenceItem]:
        for item in v:
            if not item.metric or item.metric == "UNKNOWN":
                raise ValueError(f"Free-floating evidence rejected: claim '{item.claim}' has no backing metric.")
            if not item.is_verified:
                raise ValueError(f"Fabricated evidence rejected: '{item.claim}' failed telemetry verification.")
        return v
