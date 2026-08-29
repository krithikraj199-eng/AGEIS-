"""
AEGIS Ω — Dependency Graph Engine

Builds and queries a NetworkX directed graph from asset dependencies.
Supports blast-radius calculation, cascading failure simulation,
upstream/downstream traversal, and critical-path analysis.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from .models import Asset, AssetStatus


class DependencyGraph:
    """
    A directed graph where:
      edge A → B means "A depends on B"

    So if B fails, everything that depends on B (transitively)
    can be affected.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    # ──────────────────────────────────────────────────────
    # BUILD
    # ──────────────────────────────────────────────────────

    def build_from_assets(self, assets: Dict[str, Asset]):
        """Construct the directed graph from the asset map."""
        self.graph.clear()

        # Add nodes
        for aid, asset in assets.items():
            self.graph.add_node(aid, **{
                "name": asset.name,
                "type": asset.asset_type.value,
                "department": asset.department.value,
                "criticality": asset.criticality,
                "status": asset.status.value,
            })

        # Add edges:  A → B  means A depends on B
        for aid, asset in assets.items():
            for dep_id in asset.dependencies:
                if dep_id in assets:
                    self.graph.add_edge(aid, dep_id)

    # ──────────────────────────────────────────────────────
    # QUERIES
    # ──────────────────────────────────────────────────────

    def get_direct_dependencies(self, asset_id: str) -> List[str]:
        """What does this asset directly depend on?"""
        if asset_id not in self.graph:
            return []
        return list(self.graph.successors(asset_id))

    def get_direct_dependents(self, asset_id: str) -> List[str]:
        """What directly depends on this asset?"""
        if asset_id not in self.graph:
            return []
        return list(self.graph.predecessors(asset_id))

    def get_all_upstream(self, asset_id: str) -> Set[str]:
        """All transitive dependencies (things this asset needs)."""
        if asset_id not in self.graph:
            return set()
        return nx.descendants(self.graph, asset_id)

    def get_all_downstream(self, asset_id: str) -> Set[str]:
        """All transitive dependents (things that would break if this asset fails)."""
        if asset_id not in self.graph:
            return set()
        return nx.ancestors(self.graph, asset_id)

    def get_blast_radius(self, asset_id: str) -> Dict[str, Any]:
        """
        Calculate the blast radius if an asset fails.
        Returns affected assets categorized by depth level.
        """
        if asset_id not in self.graph:
            return {"total": 0, "levels": {}, "assets": []}

        affected_assets: List[Dict[str, Any]] = []
        levels: Dict[int, List[str]] = {}
        visited: Set[str] = {asset_id}
        queue: deque = deque([(asset_id, 0)])

        while queue:
            current, depth = queue.popleft()
            # Find all direct dependents of current
            for dependent in self.graph.predecessors(current):
                if dependent not in visited:
                    visited.add(dependent)
                    level = depth + 1
                    if level not in levels:
                        levels[level] = []
                    levels[level].append(dependent)

                    node_data = self.graph.nodes[dependent]
                    affected_assets.append({
                        "asset_id": dependent,
                        "name": node_data.get("name", ""),
                        "type": node_data.get("type", ""),
                        "criticality": node_data.get("criticality", 0),
                        "depth": level,
                    })
                    queue.append((dependent, level))

        # Sort by criticality descending
        affected_assets.sort(key=lambda x: x["criticality"], reverse=True)

        return {
            "source_asset": asset_id,
            "total_affected": len(affected_assets),
            "levels": {k: len(v) for k, v in levels.items()},
            "level_details": levels,
            "affected_assets": affected_assets,
            "max_depth": max(levels.keys()) if levels else 0,
        }

    def find_cascading_path(self, source_id: str, target_id: str) -> List[str]:
        """Find the failure propagation path from source to target."""
        if source_id not in self.graph or target_id not in self.graph:
            return []
        try:
            # Reverse because edges go dependent → dependency
            # but failure propagates dependency → dependent
            reverse = self.graph.reverse()
            path = nx.shortest_path(reverse, source_id, target_id)
            return path
        except nx.NetworkXNoPath:
            return []

    def find_critical_assets(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Find the most critical assets based on:
        - Number of dependents (in-degree in reverse)
        - Criticality rating
        - Betweenness centrality
        """
        centrality = nx.betweenness_centrality(self.graph)
        results = []

        for node_id in self.graph.nodes:
            data = self.graph.nodes[node_id]
            dependent_count = self.graph.in_degree(node_id)  # predecessors = dependents
            results.append({
                "asset_id": node_id,
                "name": data.get("name", ""),
                "type": data.get("type", ""),
                "criticality": data.get("criticality", 0),
                "dependent_count": dependent_count,
                "centrality": round(centrality.get(node_id, 0), 4),
                "impact_score": round(
                    data.get("criticality", 0) * 0.4 +
                    dependent_count * 0.3 +
                    centrality.get(node_id, 0) * 100 * 0.3,
                    2
                ),
            })

        results.sort(key=lambda x: x["impact_score"], reverse=True)
        return results[:top_n]

    def get_single_points_of_failure(self) -> List[str]:
        """Find nodes whose removal would disconnect the graph."""
        # Articulation points on the undirected version
        undirected = self.graph.to_undirected()
        if nx.is_connected(undirected):
            return list(nx.articulation_points(undirected))
        else:
            # Check each connected component
            spofs = []
            for component in nx.connected_components(undirected):
                sub = undirected.subgraph(component)
                if len(sub) > 2:
                    spofs.extend(nx.articulation_points(sub))
            return spofs

    def get_graph_summary(self) -> Dict[str, Any]:
        """Get a summary of the dependency graph."""
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "density": round(nx.density(self.graph), 4),
            "is_dag": nx.is_directed_acyclic_graph(self.graph),
            "connected_components": nx.number_weakly_connected_components(self.graph),
            "node_types": self._count_by_attribute("type"),
            "departments": self._count_by_attribute("department"),
        }

    def get_graph_for_visualization(self) -> Dict[str, Any]:
        """Export graph data for frontend visualization."""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "name": data.get("name", node_id),
                "type": data.get("type", "unknown"),
                "department": data.get("department", "unknown"),
                "criticality": data.get("criticality", 0),
                "status": data.get("status", "healthy"),
                "dependents_count": self.graph.in_degree(node_id),
                "dependencies_count": self.graph.out_degree(node_id),
            })

        edges = []
        for src, dst in self.graph.edges():
            edges.append({
                "source": src,
                "target": dst,
            })

        return {"nodes": nodes, "edges": edges}

    def update_node_status(self, asset_id: str, status: str):
        """Update a node's status in the graph."""
        if asset_id in self.graph:
            self.graph.nodes[asset_id]["status"] = status

    # ──────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────

    def _count_by_attribute(self, attr: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            val = data.get(attr, "unknown")
            counts[val] = counts.get(val, 0) + 1
        return counts
