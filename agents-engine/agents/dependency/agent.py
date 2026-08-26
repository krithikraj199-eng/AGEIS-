"""
Dependency Agent for AEGIS Ω.
Topological Reasoning: Performs deterministic graph traversal to compute upstream dependencies,
downstream dependents, blast radius impact, and criticality scores.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from runtime.event_bus import EventBus
from observability.telemetry import trace_span

from .graph import (
    DependencyGraphProtocol,
    InMemoryDependencyGraph,
    ServiceNode,
)
from .models import BlastRadius, DependencyOutput

logger = logging.getLogger(__name__)


class DependencyInput(BaseModel):
    """Input payload for Dependency Agent from Evidence."""
    correlation_id: str
    incident_id: str
    asset_id: str
    evidence_id: Optional[str] = None
    root_cause_candidate: Optional[str] = None
    evidence: List[Any] = Field(default_factory=list)
    historical_similarity: Optional[float] = None
    confidence: Optional[int] = None
    cryptographic_hash: Optional[str] = None
    collected_at: Optional[str] = None
    evidence_bundle: Dict[str, Any] = Field(default_factory=dict)


class DependencyAgent(BaseAgent[DependencyInput, DependencyOutput]):
    """
    Dependency Agent:
    - Uses deterministic graph traversal (BFS) to map dependencies.
    - Computes upstream dependencies and downstream dependents.
    - Calculates affected services count and blast radius score.
    - Weights criticality score based on downstream service tier impact.
    - Pluggable graph interface allowing seamless swap to Member 1's live API.
    - Publishes to 'incident.topology' for Security Agent.
    """

    name = "Dependency"
    description = "Analyzes topological graphs, blast radiuses, and downstream failure propagation."
    inbound_topic = "incident.evidence"
    outbound_topic = "incident.topology"
    input_schema = DependencyInput
    output_schema = DependencyOutput

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        graph: Optional[DependencyGraphProtocol] = None,
    ):
        super().__init__(event_bus=event_bus)
        self.graph = graph or InMemoryDependencyGraph()

    def _calculate_criticality_score(
        self,
        root_asset_id: str,
        downstream_assets: List[str],
    ) -> float:
        """
        Calculate weighted criticality score (0.1 to 1.0).
        Score increases significantly when critical downstream nodes (Auth, API, Gateway) are affected.
        """
        all_nodes = self.graph.get_all_nodes()
        total_possible_weight = sum(n.criticality_weight for n in all_nodes) if all_nodes else 1.0

        root_node = self.graph.get_node(root_asset_id)
        affected_weight = root_node.criticality_weight if root_node else 1.0

        for d_id in downstream_assets:
            d_node = self.graph.get_node(d_id)
            if d_node:
                affected_weight += d_node.criticality_weight
            else:
                affected_weight += 1.0

        # Normalize score between 0.1 and 1.0
        normalized = round(min(1.0, max(0.1, affected_weight / total_possible_weight)), 2)
        return normalized

    async def process(self, input_data: DependencyInput) -> DependencyOutput:
        """
        Execute deterministic graph traversal and blast radius assessment.
        """
        target_asset = input_data.asset_id.upper()

        # Step 1: Upstream Dependencies (what this asset relies upon)
        upstream = self.graph.get_dependencies(target_asset, recursive=True)

        # Step 2: Downstream Dependents (services that depend on this asset)
        downstream = self.graph.get_dependents(target_asset, recursive=True)

        # Step 3: Affected Services & Blast Radius Count
        affected = [target_asset] + downstream
        all_nodes = self.graph.get_all_nodes()
        total_nodes_count = max(1, len(all_nodes))

        blast_count = len(affected)
        blast_score = round(min(1.0, blast_count / total_nodes_count), 2)

        # Step 4: Weighted Criticality Score
        criticality_score = self._calculate_criticality_score(target_asset, downstream)

        # Step 5: Construct Structured BlastRadius Object
        topology_depth = len(downstream)  # depth of chain
        blast_radius = BlastRadius(
            root_asset_id=target_asset,
            affected_services=affected,
            blast_radius_count=blast_count,
            blast_radius_score=blast_score,
            upstream_dependencies=upstream,
            downstream_dependencies=downstream,
            criticality_score=criticality_score,
            topology_depth=topology_depth,
        )

        return DependencyOutput(
            incident_id=input_data.incident_id,
            correlation_id=input_data.correlation_id,
            asset_id=input_data.asset_id,
            blast_radius=blast_radius,
            upstream_dependencies=upstream,
            downstream_dependencies=downstream,
            blast_radius_score=blast_score,
            topology_graph_id=f"TOPO-{input_data.correlation_id[:8]}",
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )
