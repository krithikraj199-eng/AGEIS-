"""
Unit Tests for Investigator Agent in AEGIS Ω.
Tests multi-dimensional context collection, in-memory history store,
3-5 competing hypothesis generation, anti-hallucination evidence validation,
and cascading failure root cause identification.
"""

import asyncio
from typing import Any, Dict, List

from runtime.event_bus import EventBus
from mocks.event_generator import generate_cascading_failure, generate_event, EventType, Severity
from agents.sentinel.agent import SentinelOutput, SentinelStatus
from agents.investigator.history_store import HistoricalIncident, HistoricalIncidentStore
from agents.investigator.context_collector import collect_investigation_context, InvestigationContext
from agents.investigator.hypotheses import Hypothesis, HypothesisSet, EvidenceValidator
from agents.investigator.agent import (
    InvestigatorAgent,
    InvestigatorInput,
    InvestigatorOutput,
    GeminiHypothesisGeneratorProtocol,
)


class MockHypothesisGenerator:
    """Mock Gemini hypothesis generator that returns controlled hypothesis sets for testing."""

    def __init__(self, hypotheses: List[Hypothesis]):
        self.hypotheses = hypotheses
        self.call_count = 0

    async def generate_hypotheses(self, context: InvestigationContext) -> List[Hypothesis]:
        self.call_count += 1
        return list(self.hypotheses)


def test_historical_incident_store():
    """Verify in-memory historical incident store retrieves relevant past incident records."""
    store = HistoricalIncidentStore()
    all_incidents = store.get_all()
    assert len(all_incidents) >= 4

    # Search by asset
    db_incidents = store.find_similar_incidents(asset_id="DATABASE-01")
    assert len(db_incidents) > 0
    assert db_incidents[0].affected_asset == "DATABASE-01"

    # Search by symptom
    auth_incidents = store.find_similar_incidents(asset_id="UNKNOWN", event_types=["LOGIN_FAILURE"])
    assert len(auth_incidents) > 0


def test_investigation_context_collection():
    """Verify context collector aggregates events, metrics, configs, deployments, and history."""
    cascade = generate_cascading_failure(correlation_id="test-ctx-1")
    events = [e.to_dict() for e in cascade]

    ctx = collect_investigation_context(
        incident_id="INC-test-ctx-1",
        correlation_id="test-ctx-1",
        asset_id="DATABASE-01",
        triggering_events=events,
    )

    assert ctx.incident_id == "INC-test-ctx-1"
    assert len(ctx.recent_events) == 4
    assert "DATABASE-01" in ctx.recent_metrics
    assert ctx.recent_metrics["DATABASE-01"]["connection_pool_usage_pct"] == 100.0
    assert len(ctx.configuration_changes) > 0
    assert len(ctx.deployment_changes) > 0
    assert "AUTH-01" in ctx.dependency_information
    assert len(ctx.historical_incidents) > 0


def test_competing_hypotheses_count_enforcement():
    """Verify that the system enforces 3 to 5 hypotheses and rejects a single hypothesis."""
    h1 = Hypothesis(
        explanation="Cause 1",
        supporting_evidence=[],
        contradicting_evidence=[],
        confidence=80,
    )
    h2 = Hypothesis(
        explanation="Cause 2",
        supporting_evidence=[],
        contradicting_evidence=[],
        confidence=50,
    )
    h3 = Hypothesis(
        explanation="Cause 3",
        supporting_evidence=[],
        contradicting_evidence=[],
        confidence=30,
    )

    # Valid set (3 hypotheses)
    valid_set = HypothesisSet(hypotheses=[h1, h2, h3])
    assert len(valid_set.hypotheses) == 3

    # Invalid: Only 1 hypothesis (must be rejected)
    rejected_single = False
    try:
        HypothesisSet(hypotheses=[h1])
    except ValueError as exc:
        rejected_single = True
        assert "Must produce between 3 and 5 competing hypotheses" in str(exc)
    assert rejected_single is True

    # Invalid: 6 hypotheses (exceeds limit)
    rejected_six = False
    try:
        HypothesisSet(hypotheses=[h1, h2, h3, h1, h2, h3])
    except ValueError:
        rejected_six = True
    assert rejected_six is True


def test_anti_hallucination_grounded_evidence():
    """Verify that evidence citing valid observed metrics and events passes validation."""
    cascade = generate_cascading_failure(correlation_id="grounding-test")
    ctx = collect_investigation_context(
        incident_id="INC-grounding-1",
        correlation_id="grounding-test",
        asset_id="DATABASE-01",
        triggering_events=[e.to_dict() for e in cascade],
    )

    validator = EvidenceValidator(context=ctx)

    grounded_hypothesis = Hypothesis(
        explanation="Database pool exhaustion caused cascading timeout",
        supporting_evidence=[
            "DATABASE_TIMEOUT event observed on DATABASE-01",
            "DATABASE-01 query_latency_ms=32400.0",
            "connection_pool_usage_pct=100.0 observed on DATABASE-01",
        ],
        contradicting_evidence=[],
        confidence=90,
    )

    validated = validator.validate_hypothesis(grounded_hypothesis)
    assert validated.is_grounded is True
    assert len(validated.grounding_validation_errors) == 0


def test_anti_hallucination_rejects_fabricated_evidence():
    """Verify that hallucinated metrics or non-existent events are flagged and rejected."""
    cascade = generate_cascading_failure(correlation_id="hallucination-test")
    ctx = collect_investigation_context(
        incident_id="INC-hallucination-1",
        correlation_id="hallucination-test",
        asset_id="DATABASE-01",
        triggering_events=[e.to_dict() for e in cascade],
    )

    validator = EvidenceValidator(context=ctx)

    hallucinated_hypothesis = Hypothesis(
        explanation="Alien cosmic ray bit-flip on GPU memory",
        supporting_evidence=[
            "quantum_flux_hz=9999.0 detected on UNKNOWN-CORE",
            "CORE_MELTDOWN_ALERT received",
        ],
        contradicting_evidence=[
            "gpu_temperature_celsius=1000.0",
        ],
        confidence=40,
    )

    validated = validator.validate_hypothesis(hallucinated_hypothesis)
    assert validated.is_grounded is False
    assert len(validated.grounding_validation_errors) > 0
    assert any("quantum_flux_hz" in err for err in validated.grounding_validation_errors)

    # Filter with reject_ungrounded=True
    filtered = validator.validate_hypothesis_set([hallucinated_hypothesis], reject_ungrounded=True)
    assert len(filtered) == 0


def test_cascading_failure_investigation():
    """
    Test full investigation of cascading failure scenario:
    DATABASE-01 -> AUTH-01 -> API-01 -> PORTAL-01
    Verifies root cause is identified while preserving competing hypotheses.
    """
    async def _test():
        bus = EventBus()
        agent = InvestigatorAgent(event_bus=bus)

        cascade = generate_cascading_failure(correlation_id="cascade-inv-123")
        triggering_events = [e.to_dict() for e in cascade]

        # Sentinel sends triage output to Investigator
        sentinel_input = InvestigatorInput(
            correlation_id="cascade-inv-123",
            incident_id="INC-cascade-inv-123",
            asset_id="DATABASE-01",
            status="CRITICAL",
            summary="Cascading failure across DB, Auth, API, and Portal",
            triggering_events=triggering_events,
        )

        output: InvestigatorOutput = await agent.process(sentinel_input)

        assert output.incident_id == "INC-cascade-inv-123"
        assert len(output.hypotheses) >= 3
        assert len(output.hypotheses) <= 5

        # Check confidence scores are all within 0-100
        for h in output.hypotheses:
            assert 0 <= h.confidence <= 100
            assert len(h.explanation) > 0
            assert isinstance(h.supporting_evidence, list)
            assert isinstance(h.contradicting_evidence, list)

        # Verify that at least one hypothesis identifies the DATABASE root cause
        db_root_causes = [
            h for h in output.hypotheses
            if "database" in h.explanation.lower() or "pool" in h.explanation.lower()
        ]
        assert len(db_root_causes) >= 1
        assert db_root_causes[0].confidence >= 70

        # Verify that competing hypotheses exist
        competing_hypotheses = [
            h for h in output.hypotheses
            if "auth" in h.explanation.lower() or "api" in h.explanation.lower() or "network" in h.explanation.lower()
        ]
        assert len(competing_hypotheses) >= 2

        # Verify all hypotheses pass anti-hallucination grounding
        for h in output.hypotheses:
            assert h.is_grounded is True

    asyncio.run(_test())


def test_investigator_event_bus_wiring():
    """Verify Investigator receives from incident.triage and publishes to incident.diagnostics."""
    async def _test():
        bus = EventBus()
        published_diagnostics = []
        bus.subscribe("incident.diagnostics", lambda ev: published_diagnostics.append(ev))

        agent = InvestigatorAgent(event_bus=bus)
        agent.start()

        event = generate_event(
            asset_id="DATABASE-01",
            event_type=EventType.DATABASE_TIMEOUT,
            severity=Severity.CRITICAL,
        )

        sentinel_out = SentinelOutput(
            incident_id="INC-wiring-001",
            status=SentinelStatus.CRITICAL,
            triggering_events=[event.to_dict()],
            summary="Critical database timeout",
            correlation_id=event.correlation_id,
            asset_id=event.asset_id,
        )

        # Publish to incident.triage
        await bus.publish("incident.triage", sentinel_out)

        assert len(published_diagnostics) == 1
        diag = published_diagnostics[0]
        assert diag.incident_id == "INC-wiring-001"
        assert len(diag.hypotheses) >= 3

        agent.stop()

    asyncio.run(_test())
