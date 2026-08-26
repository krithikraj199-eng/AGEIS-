"""
Unit Tests for Dependency Agent in AEGIS Ω.
Tests deterministic graph traversal, multi-hop dependencies, leaf nodes,
unknown assets, blast radius calculations, and criticality scoring.
"""

import asyncio
from typing import List, Optional

from runtime.event_bus import EventBus
from agents.dependency.graph import (
    DependencyGraphProtocol,
    InMemoryDependencyGraph,
    ServiceNode,
)
from agents.dependency.models import BlastRadius, DependencyOutput
from agents.dependency.agent import DependencyAgent, DependencyInput


def test_multi_hop_dependency_traversal():
    """
    Verify multi-hop graph traversal for:
    DATABASE-01 -> AUTH-01 -> API-01 -> PORTAL-01
    """
    graph = InMemoryDependencyGraph()

    # 1. DATABASE-01: Root of the cascade
    upstream_db = graph.get_dependencies("DATABASE-01", recursive=True)
    downstream_db = graph.get_dependents("DATABASE-01", recursive=True)
    assert len(upstream_db) == 0
    assert "AUTH-01" in downstream_db
    assert "API-01" in downstream_db
    assert "PORTAL-01" in downstream_db

    # 2. AUTH-01: Middle tier
    upstream_auth = graph.get_dependencies("AUTH-01", recursive=True)
    downstream_auth = graph.get_dependents("AUTH-01", recursive=True)
    assert "DATABASE-01" in upstream_auth
    assert "API-01" in downstream_auth
    assert "PORTAL-01" in downstream_auth

    # 3. API-01: Ingress tier
    upstream_api = graph.get_dependencies("API-01", recursive=True)
    downstream_api = graph.get_dependents("API-01", recursive=True)
    assert "AUTH-01" in upstream_api
    assert "DATABASE-01" in upstream_api
    assert downstream_api == ["PORTAL-01"]


def test_leaf_node_traversal():
    """Verify leaf node has upstream dependencies but zero downstream dependents."""
    graph = InMemoryDependencyGraph()

    upstream_portal = graph.get_dependencies("PORTAL-01", recursive=True)
    downstream_portal = graph.get_dependents("PORTAL-01", recursive=True)

    # PORTAL-01 is a leaf node
    assert len(downstream_portal) == 0
    assert "API-01" in upstream_portal
    assert "AUTH-01" in upstream_portal
    assert "DATABASE-01" in upstream_portal


def test_unknown_asset_handling():
    """Verify unknown assets are handled gracefully without raising exceptions."""
    graph = InMemoryDependencyGraph()

    upstream = graph.get_dependencies("UNKNOWN-ASSET-999")
    downstream = graph.get_dependents("UNKNOWN-ASSET-999")
    node = graph.get_node("UNKNOWN-ASSET-999")

    assert upstream == []
    assert downstream == []
    assert node is None


def test_blast_radius_calculation():
    """Verify structured BlastRadius object and affected service counts."""
    async def _test():
        agent = DependencyAgent()

        # Input for DATABASE-01
        inp_db = DependencyInput(
            correlation_id="corr-topo-1",
            incident_id="INC-topo-1",
            asset_id="DATABASE-01",
        )
        out_db: DependencyOutput = await agent.process(inp_db)

        assert out_db.blast_radius.root_asset_id == "DATABASE-01"
        assert "DATABASE-01" in out_db.blast_radius.affected_services
        assert "AUTH-01" in out_db.blast_radius.affected_services
        assert "API-01" in out_db.blast_radius.affected_services
        assert "PORTAL-01" in out_db.blast_radius.affected_services
        assert out_db.blast_radius.blast_radius_count >= 4
        assert out_db.blast_radius.blast_radius_score > 0.50

        # Input for PORTAL-01 (leaf node)
        inp_portal = DependencyInput(
            correlation_id="corr-topo-2",
            incident_id="INC-topo-2",
            asset_id="PORTAL-01",
        )
        out_portal: DependencyOutput = await agent.process(inp_portal)

        assert out_portal.blast_radius.root_asset_id == "PORTAL-01"
        assert out_portal.blast_radius.affected_services == ["PORTAL-01"]
        assert out_portal.blast_radius.blast_radius_count == 1
        assert out_portal.blast_radius.downstream_dependencies == []

    asyncio.run(_test())


def test_criticality_score_ordering():
    """Verify criticality score is significantly higher when mission-critical root/downstream nodes are affected."""
    async def _test():
        agent = DependencyAgent()

        out_db = await agent.process(DependencyInput(correlation_id="c1", incident_id="i1", asset_id="DATABASE-01"))
        out_portal = await agent.process(DependencyInput(correlation_id="c2", incident_id="i2", asset_id="PORTAL-01"))

        # Database failure cascades to entire stack -> higher criticality than edge portal failure
        assert out_db.blast_radius.criticality_score > out_portal.blast_radius.criticality_score
        assert out_db.blast_radius.criticality_score >= 0.70

    asyncio.run(_test())


def test_pluggable_graph_interface():
    """Verify DependencyAgent can seamlessly accept a custom graph client (e.g. Member 1 API client)."""
    class CustomMember1Graph:
        def get_dependencies(self, asset_id: str, recursive: bool = True) -> List[str]:
            return ["CUSTOM-UPSTREAM"]

        def get_dependents(self, asset_id: str, recursive: bool = True) -> List[str]:
            return ["CUSTOM-DOWNSTREAM-1", "CUSTOM-DOWNSTREAM-2"]

        def get_node(self, asset_id: str) -> Optional[ServiceNode]:
            return ServiceNode(asset_id=asset_id, service_type="custom_service", criticality_weight=4.0, tier=2)

        def get_all_nodes(self) -> List[ServiceNode]:
            return [
                ServiceNode(asset_id="ASSET-A", service_type="a", criticality_weight=2.0),
                ServiceNode(asset_id="ASSET-B", service_type="b", criticality_weight=2.0),
            ]

    async def _test():
        custom_graph = CustomMember1Graph()
        agent = DependencyAgent(graph=custom_graph)

        out = await agent.process(DependencyInput(correlation_id="c-cust", incident_id="i-cust", asset_id="TEST-SERVICE"))
        assert out.upstream_dependencies == ["CUSTOM-UPSTREAM"]
        assert out.downstream_dependencies == ["CUSTOM-DOWNSTREAM-1", "CUSTOM-DOWNSTREAM-2"]
        assert "CUSTOM-DOWNSTREAM-1" in out.blast_radius.affected_services

    asyncio.run(_test())


def test_dependency_agent_event_bus_wiring():
    """Verify DependencyAgent receives on incident.evidence and publishes to incident.topology."""
    async def _test():
        bus = EventBus()
        published_topology = []
        bus.subscribe("incident.topology", lambda ev: published_topology.append(ev))

        agent = DependencyAgent(event_bus=bus)
        agent.start()

        evidence_input = DependencyInput(
            correlation_id="wiring-topo-1",
            incident_id="INC-wiring-topo-1",
            asset_id="DATABASE-01",
            evidence_id="EVD-wiring-1",
            cryptographic_hash="hash123",
        )

        await bus.publish("incident.evidence", evidence_input)

        assert len(published_topology) == 1
        topo_out: DependencyOutput = published_topology[0]
        assert topo_out.incident_id == "INC-wiring-topo-1"
        assert topo_out.blast_radius.blast_radius_count >= 4
        assert topo_out.topology_graph_id is not None

        agent.stop()

    asyncio.run(_test())
