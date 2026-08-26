"""
Dependency Models and Structured BlastRadius Schema for AEGIS Ω.
"""

from typing import List
from pydantic import BaseModel, Field


class BlastRadius(BaseModel):
    """
    Structured BlastRadius representation calculated via deterministic graph traversal.
    """
    root_asset_id: str = Field(
        description="Originating asset undergoing failure or investigation",
    )
    affected_services: List[str] = Field(
        description="Comprehensive list of services impacted by this asset failure (root + downstream)",
    )
    blast_radius_count: int = Field(
        description="Total count of impacted services",
    )
    blast_radius_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized blast radius score (0.0 to 1.0)",
    )
    upstream_dependencies: List[str] = Field(
        description="Services that this asset requires to operate",
    )
    downstream_dependencies: List[str] = Field(
        description="Services that rely upon this asset and will fail if it crashes",
    )
    criticality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Weighted criticality score (0.0 to 1.0) based on downstream tier impact",
    )
    topology_depth: int = Field(
        description="Maximum depth of the downstream dependency cascade",
    )


class DependencyOutput(BaseModel):
    """
    Output payload from Dependency Agent for downstream resilience agents.
    """
    incident_id: str
    correlation_id: str
    asset_id: str
    blast_radius: BlastRadius
    upstream_dependencies: List[str] = Field(default_factory=list)
    downstream_dependencies: List[str] = Field(default_factory=list)
    blast_radius_score: float = Field(ge=0.0, le=1.0)
    topology_graph_id: str
    analyzed_at: str
