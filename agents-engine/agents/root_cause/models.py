"""
Root Cause Synthesis Models and Schemas for AEGIS Ω.
Enforces strict traceability to Evidence, Dependency, and Security inputs.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from agents.dependency.models import BlastRadius


class RootCauseOutput(BaseModel):
    """
    Required output schema for Root Cause Engine:
    { root_cause, confidence, affected_systems, supporting_evidence, classification, blast_radius }
    """
    incident_id: str
    correlation_id: str
    root_asset_id: str
    root_cause: str = Field(
        description="Synthesized root cause explanation traced from Evidence and Dependency topology",
    )
    confidence: float = Field(
        ge=0.0,
        le=100.0,
        description="Confidence score (0.0 to 100.0) synthesized from input agents",
    )
    affected_systems: List[str] = Field(
        description="List of impacted assets traced directly from Dependency blast radius",
    )
    supporting_evidence: List[str] = Field(
        description="List of verified factual claims traced directly from Evidence Agent",
    )
    classification: str = Field(
        description="Incident category traced directly from Security Agent classification",
    )
    blast_radius: Union[BlastRadius, Dict[str, Any]] = Field(
        description="Structured blast radius object traced directly from Dependency Agent",
    )
    discrepancy_flag: bool = Field(
        default=False,
        description="True if conflicting findings exist between Security and Evidence agents",
    )
    discrepancy_details: Optional[str] = Field(
        default=None,
        description="Detailed description of detected discrepancy between input agents",
    )
    causal_chain: List[str] = Field(
        default_factory=list,
        description="Step-by-step causal failure progression across affected services",
    )
    primary_failure_cause: Optional[str] = None  # Downstream compatibility alias
    diagnosed_at: str
