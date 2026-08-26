"""
Unit Tests for Evidence Agent in AEGIS Ω.
Tests deterministic metric delta calculations, historical similarity scoring,
strict evidence-to-metric grounding, and rejection of fabricated/free-floating evidence.
"""

import asyncio
from typing import Any, Dict, List

from runtime.event_bus import EventBus
from mocks.event_generator import generate_cascading_failure, generate_event, EventType, Severity
from agents.evidence.delta_engine import calculate_metric_delta, HistoricalSimilarityScorer
from agents.evidence.models import EvidenceItem, EvidenceOutput
from agents.evidence.agent import EvidenceAgent, EvidenceInput


def test_metric_delta_calculations():
    """
    Test deterministic metric delta calculation in pure Python.
    Prompt example: before = 100, after = 417 -> percentage = +317.0%
    """
    # 1. Prompt Example
    d1 = calculate_metric_delta(metric_name="test_metric", before=100.0, after=417.0)
    assert d1.before_value == 100.0
    assert d1.after_value == 417.0
    assert d1.absolute_change == 317.0
    assert d1.percentage_change == 317.0
    assert d1.formatted_delta == "+317.0%"

    # 2. Latency spike: before = 15ms, after = 32400ms
    d2 = calculate_metric_delta(metric_name="query_latency_ms", before=15.0, after=32400.0)
    assert d2.absolute_change == 32385.0
    assert d2.percentage_change == 215900.0
    assert "+215900.0%" in d2.formatted_delta

    # 3. Connection drop / negative delta: before = 500, after = 50
    d3 = calculate_metric_delta(metric_name="active_connections", before=500.0, after=50.0)
    assert d3.absolute_change == -450.0
    assert d3.percentage_change == -90.0
    assert d3.formatted_delta == "-90.0%"

    # 4. Zero baseline: before = 0, after = 10
    d4 = calculate_metric_delta(metric_name="deadlocks", before=0.0, after=10.0)
    assert d4.percentage_change == 100.0


def test_evidence_output_schema_structure():
    """Verify EvidenceOutput contains root_cause_candidate, evidence, historical_similarity, confidence."""
    item = EvidenceItem(
        claim="Database query latency spiked significantly",
        metric="query_latency_ms",
        before=15.0,
        after=32400.0,
        delta="+215900.0%",
        source="sensor_database-01",
    )

    output = EvidenceOutput(
        incident_id="INC-test-123",
        correlation_id="corr-test-123",
        asset_id="DATABASE-01",
        evidence_id="EVD-test-123",
        root_cause_candidate="DATABASE-01: Connection Pool Exhaustion",
        evidence=[item],
        historical_similarity=0.85,
        confidence=90,
        cryptographic_hash="abc123hash",
        collected_at="2026-08-25T14:00:00Z",
    )

    data = output.model_dump()
    assert "root_cause_candidate" in data
    assert "evidence" in data
    assert len(data["evidence"]) == 1
    assert data["evidence"][0]["metric"] == "query_latency_ms"
    assert data["evidence"][0]["before"] == 15.0
    assert data["evidence"][0]["after"] == 32400.0
    assert "historical_similarity" in data
    assert data["historical_similarity"] == 0.85
    assert "confidence" in data
    assert data["confidence"] == 90


def test_historical_similarity_scorer():
    """Verify historical similarity scoring calculates realistic normalized score."""
    scorer = HistoricalSimilarityScorer()

    # Highly matching metrics and symptoms for database timeout
    score_db = scorer.calculate_similarity(
        asset_id="DATABASE-01",
        observed_metrics={"connection_pool_usage_pct": 100.0, "query_latency_ms": 32400.0},
        observed_events=["DATABASE_TIMEOUT"],
    )
    assert 0.0 <= score_db <= 1.0
    assert score_db >= 0.70  # strong match to HIST-INC-2026-001


def test_fabricated_evidence_rejection():
    """Verify that unbacked / fabricated claims are filtered out and cannot create free-floating evidence."""
    async def _test():
        bus = EventBus()
        agent = EvidenceAgent(event_bus=bus)

        # Context only has query_latency_ms and connection_pool_usage_pct
        input_data = EvidenceInput(
            correlation_id="test-fab-1",
            incident_id="INC-test-fab-1",
            asset_id="DATABASE-01",
            hypotheses=[
                {
                    "explanation": "Real DB issue",
                    "supporting_evidence": [
                        "DATABASE-01 query_latency_ms=32400.0",
                        "Fabricated alien signal with zero telemetry backing",
                        "quantum_flux_nonexistent_metric=999.0",
                    ],
                }
            ],
            investigation_context={
                "recent_metrics": {
                    "DATABASE-01": {"query_latency_ms": 32400.0, "connection_pool_usage_pct": 100.0}
                }
            },
        )

        output = await agent.process(input_data)

        # Only the grounded claim matching 'query_latency_ms' should pass
        metrics_in_evidence = [e.metric for e in output.evidence]
        assert "query_latency_ms" in metrics_in_evidence
        # Fabricated non-existent metrics MUST NOT be in evidence
        assert "quantum_flux_nonexistent_metric" not in metrics_in_evidence
        assert "alien_signal" not in metrics_in_evidence

        # Every item in output.evidence MUST map to a real metric
        for e in output.evidence:
            assert e.metric in ["query_latency_ms", "connection_pool_usage_pct"]
            assert e.is_verified is True

    asyncio.run(_test())


def test_evidence_agent_event_bus_wiring():
    """Verify EvidenceAgent receives on incident.diagnostics and publishes to incident.evidence."""
    async def _test():
        bus = EventBus()
        published_evidence = []
        bus.subscribe("incident.evidence", lambda ev: published_evidence.append(ev))

        agent = EvidenceAgent(event_bus=bus)
        agent.start()

        diag_input = EvidenceInput(
            correlation_id="wiring-evd-1",
            incident_id="INC-wiring-evd-1",
            asset_id="DATABASE-01",
            hypotheses=[
                {
                    "explanation": "Database query timeout",
                    "supporting_evidence": ["query_latency_ms=32400.0"],
                }
            ],
            metric_correlations={"query_latency_ms": 32400.0},
        )

        await bus.publish("incident.diagnostics", diag_input)

        assert len(published_evidence) == 1
        ev_out: EvidenceOutput = published_evidence[0]
        assert ev_out.incident_id == "INC-wiring-evd-1"
        assert len(ev_out.evidence) >= 1
        assert ev_out.cryptographic_hash is not None

        agent.stop()

    asyncio.run(_test())
