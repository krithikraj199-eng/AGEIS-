"""
Unit Tests for Root Cause Engine in AEGIS Ω.
Tests multi-agent synthesis, strict field traceability, discrepancy detection,
anti-fabrication guarantees, and blast radius propagation.
"""

import asyncio
from typing import Any, Dict, List

from runtime.event_bus import EventBus
from agents.dependency.models import BlastRadius
from agents.security.models import IncidentClassification
from agents.root_cause.models import RootCauseOutput
from agents.root_cause.synthesizer import (
    DeterministicRootCauseSynthesizer,
    GeminiRootCauseSummarizerProtocol,
)
from agents.root_cause.agent import RootCauseAgent, RootCauseInput


def test_field_traceability_from_upstream_agents():
    """
    Verify that every output field strictly traces back to Evidence, Dependency, or Security.
    """
    async def _test():
        agent = RootCauseAgent()

        evidence_items = [
            {"claim": "DATABASE-01 query_latency_ms=32400.0", "metric": "query_latency_ms", "delta": "+215900.0%"},
            {"claim": "DATABASE-01 connection_pool_usage_pct=100.0", "metric": "connection_pool_usage_pct", "delta": "+400.0%"},
        ]
        blast_radius = BlastRadius(
            root_asset_id="DATABASE-01",
            affected_services=["DATABASE-01", "AUTH-01", "API-01", "PORTAL-01"],
            blast_radius_count=4,
            blast_radius_score=0.80,
            upstream_dependencies=[],
            downstream_dependencies=["AUTH-01", "API-01", "PORTAL-01"],
            criticality_score=0.85,
            topology_depth=3,
        )

        input_data = RootCauseInput(
            correlation_id="trace-corr-1",
            incident_id="INC-trace-1",
            asset_id="DATABASE-01",
            classification=IncidentClassification.OPERATIONAL_FAILURE.value,
            risk_flag=False,
            threat_level="LOW",
            is_security_incident=False,
            blast_radius=blast_radius,
            downstream_dependencies=["AUTH-01", "API-01", "PORTAL-01"],
            root_cause_candidate="Database connection pool exhaustion and query timeouts on DATABASE-01",
            evidence=evidence_items,
            confidence=92,
        )

        output: RootCauseOutput = await agent.process(input_data)

        # 1. Trace root_cause -> Evidence candidate
        assert output.root_cause == "Database connection pool exhaustion and query timeouts on DATABASE-01"

        # 2. Trace confidence -> Evidence confidence
        assert output.confidence == 92.0

        # 3. Trace affected_systems -> Dependency blast radius
        assert output.affected_systems == ["DATABASE-01", "AUTH-01", "API-01", "PORTAL-01"]

        # 4. Trace supporting_evidence -> Evidence items
        assert any("query_latency_ms=32400.0" in claim for claim in output.supporting_evidence)
        assert any("connection_pool_usage_pct=100.0" in claim for claim in output.supporting_evidence)

        # 5. Trace classification -> Security classification
        assert output.classification == IncidentClassification.OPERATIONAL_FAILURE.value

        # 6. Trace blast_radius -> Dependency blast radius
        assert output.blast_radius.blast_radius_count == 4

        # 7. No discrepancy in clean operational case
        assert output.discrepancy_flag is False

    asyncio.run(_test())


def test_discrepancy_detection_between_security_and_evidence():
    """
    Verify that conflicting Security (SECURITY_EVENT) vs Evidence (pure operational telemetry)
    produces a discrepancy_flag instead of silently choosing one.
    """
    async def _test():
        agent = RootCauseAgent()

        # Evidence only has standard operational metrics (query latency, pool exhaustion)
        evidence_items = [
            {"claim": "DATABASE-01 query_latency_ms=32400.0", "metric": "query_latency_ms", "delta": "+215900.0%"},
        ]
        blast_radius = BlastRadius(
            root_asset_id="DATABASE-01",
            affected_services=["DATABASE-01", "AUTH-01"],
            blast_radius_count=2,
            blast_radius_score=0.50,
            upstream_dependencies=[],
            downstream_dependencies=["AUTH-01"],
            criticality_score=0.60,
            topology_depth=1,
        )

        # Security says SECURITY_EVENT, but Evidence shows pure operational pool exhaustion
        input_data = RootCauseInput(
            correlation_id="disc-corr-1",
            incident_id="INC-disc-1",
            asset_id="DATABASE-01",
            classification=IncidentClassification.SECURITY_EVENT.value,
            risk_flag=True,
            threat_level="HIGH",
            is_security_incident=True,
            detected_patterns=[],  # no actual exploit signatures in log
            blast_radius=blast_radius,
            root_cause_candidate="Database connection pool exhaustion on DATABASE-01",
            evidence=evidence_items,
            confidence=85,
        )

        output: RootCauseOutput = await agent.process(input_data)

        # Discrepancy MUST be detected and flagged
        assert output.discrepancy_flag is True
        assert output.discrepancy_details is not None
        assert "Discrepancy detected" in output.discrepancy_details
        assert "SECURITY_EVENT" in output.discrepancy_details
        assert "operational" in output.discrepancy_details

        # Both perspectives are preserved
        assert output.classification == IncidentClassification.SECURITY_EVENT.value
        assert "query_latency_ms=32400.0" in output.supporting_evidence[0]

    asyncio.run(_test())


def test_no_fabricated_claims():
    """Verify that only ground-truth evidence provided to the agent is present in output."""
    async def _test():
        agent = RootCauseAgent()

        evidence_items = [
            {"claim": "DATABASE-01 memory_used_pct=98.5", "metric": "memory_used_pct", "delta": "+40.0%"},
        ]

        input_data = RootCauseInput(
            correlation_id="no-fab-1",
            incident_id="INC-no-fab-1",
            asset_id="DATABASE-01",
            classification=IncidentClassification.OPERATIONAL_FAILURE.value,
            root_cause_candidate="High memory pressure",
            evidence=evidence_items,
            confidence=80,
        )

        output: RootCauseOutput = await agent.process(input_data)

        # Assert no unexpected claims exist in supporting_evidence
        assert len(output.supporting_evidence) == 1
        assert "DATABASE-01 memory_used_pct=98.5" in output.supporting_evidence[0]
        assert "hallucinated_metric" not in str(output.supporting_evidence)

    asyncio.run(_test())


def test_blast_radius_propagation():
    """Verify blast radius and topology depth propagate accurately."""
    async def _test():
        agent = RootCauseAgent()

        blast_radius = BlastRadius(
            root_asset_id="DATABASE-01",
            affected_services=["DATABASE-01", "AUTH-01", "API-01", "PORTAL-01"],
            blast_radius_count=4,
            blast_radius_score=0.85,
            upstream_dependencies=[],
            downstream_dependencies=["AUTH-01", "API-01", "PORTAL-01"],
            criticality_score=0.90,
            topology_depth=3,
        )

        input_data = RootCauseInput(
            correlation_id="blast-prop-1",
            incident_id="INC-blast-1",
            asset_id="DATABASE-01",
            blast_radius=blast_radius,
            confidence=90,
        )

        output: RootCauseOutput = await agent.process(input_data)

        assert output.affected_systems == ["DATABASE-01", "AUTH-01", "API-01", "PORTAL-01"]
        assert output.blast_radius.blast_radius_count == 4
        assert output.blast_radius.topology_depth == 3
        assert len(output.causal_chain) == 4  # Root + 3 downstream steps

    asyncio.run(_test())


def test_root_cause_agent_event_bus_wiring():
    """Verify RootCauseAgent receives on incident.security_cleared and publishes to incident.root_cause."""
    async def _test():
        bus = EventBus()
        published_root_causes = []
        bus.subscribe("incident.root_cause", lambda ev: published_root_causes.append(ev))

        agent = RootCauseAgent(event_bus=bus)
        agent.start()

        sec_input = RootCauseInput(
            correlation_id="rc-wiring-1",
            incident_id="INC-rc-wiring-1",
            asset_id="DATABASE-01",
            classification=IncidentClassification.OPERATIONAL_FAILURE.value,
            root_cause_candidate="Database connection pool exhausted",
        )

        await bus.publish("incident.security_cleared", sec_input)

        assert len(published_root_causes) == 1
        rc_out: RootCauseOutput = published_root_causes[0]
        assert rc_out.incident_id == "INC-rc-wiring-1"
        assert rc_out.root_cause == "Database connection pool exhausted"
        assert rc_out.confidence >= 50.0

        agent.stop()

    asyncio.run(_test())
