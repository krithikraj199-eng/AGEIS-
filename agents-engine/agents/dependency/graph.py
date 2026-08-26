"""
Dependency Graph Interface and In-Memory Topology for AEGIS Ω Dependency Agent.
Designed as a pluggable abstraction that can be swapped with Member 1's real API client seamlessly.
"""

from collections import deque
from typing import Dict, List, Optional, Protocol, Set
from pydantic import BaseModel, Field


class ServiceNode(BaseModel):
    """Metadata for an individual service node in the dependency topology."""
    asset_id: str
    service_type: str
    criticality_weight: float = Field(
        default=1.0,
        description="Weight indicating service tier importance (1.0 to 5.0)",
    )
    tier: int = Field(
        default=1,
        description="Architectural tier: 1=Data, 2=Auth, 3=Core API, 4=Edge/Portal",
    )


class DependencyGraphProtocol(Protocol):
    """
    Pluggable dependency graph protocol.
    Replacing the in-memory graph with Member 1's live API only requires
    providing an implementation of this protocol.
    """

    def get_dependencies(self, asset_id: str, recursive: bool = True) -> List[str]:
        """
        Retrieve upstream dependencies that the given asset depends on.
        Example: PORTAL-01 depends on API-01, AUTH-01, and DATABASE-01.
        """
        ...

    def get_dependents(self, asset_id: str, recursive: bool = True) -> List[str]:
        """
        Retrieve downstream dependents that depend on the given asset.
        Example: DATABASE-01 failure cascades to AUTH-01, API-01, and PORTAL-01.
        """
        ...

    def get_node(self, asset_id: str) -> Optional[ServiceNode]:
        """Retrieve metadata for a specific service node."""
        ...

    def get_all_nodes(self) -> List[ServiceNode]:
        """Retrieve all nodes in the topology."""
        ...


class InMemoryDependencyGraph:
    """
    Deterministic in-memory graph implementation supporting directed graph traversal.
    Topology:
        DATABASE-01 -> AUTH-01 -> API-01 -> PORTAL-01
    """

    def __init__(self):
        # Forward edges: asset -> downstream dependents
        # i.e., who depends on this asset? (failure propagates forward)
        self._forward_adj: Dict[str, List[str]] = {
            "DATABASE-01": ["AUTH-01", "WORKER-01"],
            "AUTH-01": ["API-01"],
            "API-01": ["PORTAL-01"],
            "PORTAL-01": [],
            "CACHE-01": ["API-01"],
            "PAYMENT-01": ["API-01"],
            "WORKER-01": [],
        }

        # Reverse edges: asset -> upstream dependencies
        # i.e., what does this asset require to function?
        self._reverse_adj: Dict[str, List[str]] = {}
        self._rebuild_reverse_index()

        # Node metadata registry
        self._nodes: Dict[str, ServiceNode] = {
            "DATABASE-01": ServiceNode(asset_id="DATABASE-01", service_type="database", criticality_weight=5.0, tier=1),
            "AUTH-01": ServiceNode(asset_id="AUTH-01", service_type="auth_service", criticality_weight=4.5, tier=2),
            "API-01": ServiceNode(asset_id="API-01", service_type="api_gateway", criticality_weight=4.0, tier=3),
            "PORTAL-01": ServiceNode(asset_id="PORTAL-01", service_type="web_portal", criticality_weight=3.0, tier=4),
            "CACHE-01": ServiceNode(asset_id="CACHE-01", service_type="in_memory_cache", criticality_weight=2.5, tier=2),
            "PAYMENT-01": ServiceNode(asset_id="PAYMENT-01", service_type="payment_service", criticality_weight=4.8, tier=3),
            "WORKER-01": ServiceNode(asset_id="WORKER-01", service_type="background_worker", criticality_weight=2.0, tier=2),
        }

    def _rebuild_reverse_index(self) -> None:
        """Construct reverse adjacency list for upstream dependency lookups."""
        self._reverse_adj = {k: [] for k in self._forward_adj.keys()}
        for parent, children in self._forward_adj.items():
            for child in children:
                if child not in self._reverse_adj:
                    self._reverse_adj[child] = []
                self._reverse_adj[child].append(parent)

    def get_dependencies(self, asset_id: str, recursive: bool = True) -> List[str]:
        """
        Get upstream dependencies for asset_id (what this asset relies upon).
        Deterministic BFS traversal.
        """
        aid = asset_id.upper()
        if aid not in self._reverse_adj:
            return []

        if not recursive:
            return list(self._reverse_adj.get(aid, []))

        visited: Set[str] = set()
        queue: deque = deque(self._reverse_adj.get(aid, []))
        result: List[str] = []

        while queue:
            current = queue.popleft()
            if current not in visited and current != aid:
                visited.add(current)
                result.append(current)
                for upstream in self._reverse_adj.get(current, []):
                    if upstream not in visited:
                        queue.append(upstream)

        return result

    def get_dependents(self, asset_id: str, recursive: bool = True) -> List[str]:
        """
        Get downstream dependents for asset_id (who relies upon this asset).
        Deterministic BFS traversal.
        """
        aid = asset_id.upper()
        if aid not in self._forward_adj:
            return []

        if not recursive:
            return list(self._forward_adj.get(aid, []))

        visited: Set[str] = set()
        queue: deque = deque(self._forward_adj.get(aid, []))
        result: List[str] = []

        while queue:
            current = queue.popleft()
            if current not in visited and current != aid:
                visited.add(current)
                result.append(current)
                for downstream in self._forward_adj.get(current, []):
                    if downstream not in visited:
                        queue.append(downstream)

        return result

    def get_node(self, asset_id: str) -> Optional[ServiceNode]:
        """Retrieve node metadata or return None for unknown assets."""
        return self._nodes.get(asset_id.upper())

    def get_all_nodes(self) -> List[ServiceNode]:
        """Retrieve all nodes in the topology."""
        return list(self._nodes.values())
