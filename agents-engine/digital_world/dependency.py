"""
Dependency Graph API for Digital World Environment.
Provides upstream dependencies and downstream dependents discovery across infrastructure topology.
"""

from collections import deque
from typing import Dict, List, Optional, Set


class DependencyGraphAPI:
    """
    Member 1's Dependency Graph API interface:
    - get_dependencies(asset_id) -> upstream dependencies required by asset
    - get_dependents(asset_id) -> downstream dependents affected by asset
    """

    def __init__(self):
        # Forward edges: asset -> downstream dependents (failure propagates forward)
        self._forward_adj: Dict[str, List[str]] = {
            "DATABASE-01": ["AUTH-01", "WORKER-01"],
            "AUTH-01": ["API-01"],
            "API-01": ["PORTAL-01"],
            "PORTAL-01": [],
            "CACHE-01": ["API-01"],
            "PAYMENT-01": ["API-01"],
            "WORKER-01": [],
        }
        # Reverse edges: asset -> upstream dependencies (what does this asset require?)
        self._reverse_adj: Dict[str, List[str]] = {}
        self._rebuild_reverse_index()

    def _rebuild_reverse_index(self) -> None:
        """Construct reverse adjacency index for upstream dependency lookups."""
        self._reverse_adj = {k: [] for k in self._forward_adj.keys()}
        for parent, children in self._forward_adj.items():
            for child in children:
                if child not in self._reverse_adj:
                    self._reverse_adj[child] = []
                self._reverse_adj[child].append(parent)

    def get_dependencies(self, asset_id: str, recursive: bool = True) -> List[str]:
        """
        Retrieve upstream dependencies that the given asset depends on.
        Example: PORTAL-01 depends on API-01, AUTH-01, and DATABASE-01.
        """
        if not recursive:
            return list(self._reverse_adj.get(asset_id, []))

        visited: Set[str] = set()
        queue = deque(self._reverse_adj.get(asset_id, []))

        while queue:
            node = queue.popleft()
            if node not in visited and node != asset_id:
                visited.add(node)
                for upstream in self._reverse_adj.get(node, []):
                    if upstream not in visited:
                        queue.append(upstream)

        return sorted(list(visited))

    def get_dependents(self, asset_id: str, recursive: bool = True) -> List[str]:
        """
        Retrieve downstream dependents that depend on the given asset.
        Example: DATABASE-01 failure cascades to AUTH-01, API-01, and PORTAL-01.
        """
        if not recursive:
            return list(self._forward_adj.get(asset_id, []))

        visited: Set[str] = set()
        queue = deque(self._forward_adj.get(asset_id, []))

        while queue:
            node = queue.popleft()
            if node not in visited and node != asset_id:
                visited.add(node)
                for downstream in self._forward_adj.get(node, []):
                    if downstream not in visited:
                        queue.append(downstream)

        return sorted(list(visited))

    def get_all_assets(self) -> List[str]:
        """List all tracked asset IDs in the topology graph."""
        return sorted(list(self._forward_adj.keys()))
