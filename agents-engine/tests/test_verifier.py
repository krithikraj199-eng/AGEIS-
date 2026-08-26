"""
Unit Tests for Verifier Agent in AEGIS Ω.
Tests deterministic before/after metric verification:
  1. metric improves -> SUCCESS
  2. metric remains bad -> FAILED
  3. metric worsens -> FAILED
Tests same-metric enforcement, exact JSON schema compliance, and conditional event routing.
"""

import asyncio
from typing import Any, Dict, List

from runtime.event_bus import EventBus
from agents.verifier.models import VerificationStatus, VerifierOutput
from agents.verifier.auditor import DeterministicMetricAuditor
from agents.verifier.agent import VerifierAgent, VerifierInput


def test_metric_improves_leads_to_success():
    """Verify that a significant drop below healthy threshold yields SUCCESS."""
    status, expected_result, evidence = DeterministicMetricAuditor.verify_metric(
        metric_name="latency_ms",
        before_val=850.0,
        after_val=120.0,
    )
    assert status == VerificationStatus.SUCCESS
    assert "latency_ms <= 200.0" in expected_result
    assert "850.0" in evidence
    assert "120.0" in evidence
    assert "-85.88%" in evidence


def test_metric_remains_bad_leads_to_failed():
    """Verify that a metric remaining above SLA threshold yields FAILED."""
    status, expected_result, evidence = DeterministicMetricAuditor.verify_metric(
        metric_name="latency_ms",
        before_val=850.0,
        after_val=750.0,
    )
    assert status == VerificationStatus.FAILED
    assert "remained elevated at 750.0" in evidence


def test_metric_worsens_leads_to_failed():
    """Verify that a metric increasing post-remediation yields FAILED."""
    status, expected_result, evidence = DeterministicMetricAuditor.verify_metric(
        metric_name="latency_ms",
        before_val=850.0,
        after_val=1250.0,
    )
    assert status == VerificationStatus.FAILED
    assert "worsened post-remediation" in evidence
    assert "+47.06%" in evidence


def test_cpu_and_error_rate_deterministic_auditing():
    """Test auditing on cpu_percent and error_rate."""
    # CPU recovery
    s1, exp1, ev1 = DeterministicMetricAuditor.verify_metric("cpu_percent", 98.0, 32.0)
    assert s1 == VerificationStatus.SUCCESS
    assert "cpu_percent <= 80.0" in exp1

    # CPU still boiling
    s2, exp2, ev2 = DeterministicMetricAuditor.verify_metric("cpu_percent", 98.0, 92.0)
    assert s2 == VerificationStatus.FAILED

    # Error rate recovery
    s3, exp3, ev3 = DeterministicMetricAuditor.verify_metric("error_rate", 0.45, 0.01)
    assert s3 == VerificationStatus.SUCCESS
    assert "error_rate <= 0.05" in exp3


def test_higher_is_better_metrics_auditing():
    """Test auditing on higher-is-better metrics (throughput, availability)."""
    # Throughput recovery
    s1, exp1, ev1 = DeterministicMetricAuditor.verify_metric("throughput_rps", 50.0, 500.0, target_threshold=300.0)
    assert s1 == VerificationStatus.SUCCESS

    # Throughput dropped further
    s2, exp2, ev2 = DeterministicMetricAuditor.verify_metric("throughput_rps", 50.0, 10.0, target_threshold=300.0)
    assert s2 == VerificationStatus.FAILED


def test_verifier_output_schema_structure():
    """Verify that VerifierOutput contains status, metric, before, after, expected_result, evidence."""
    output = VerifierOutput(
        incident_id="INC-test-1",
        correlation_id="corr-test-1",
        plan_id="PLAN-01",
        status="SUCCESS",
        metric="latency_ms",
        before=850.0,
        after=120.0,
        expected_result="latency_ms <= 200.0",
        evidence="Observed metric 'latency_ms' dropped from 850.0 to 120.0 (-85.88%).",
        health_status="HEALTHY",
        metrics_normalized=True,
        verification_passed=True,
        verified_at="2026-08-25T14:50:00Z",
    )

    data = output.model_dump()
    assert data["status"] == "SUCCESS"
    assert data["metric"] == "latency_ms"
    assert data["before"] == 850.0
    assert data["after"] == 120.0
    assert data["expected_result"] == "latency_ms <= 200.0"
    assert "evidence" in data


def test_event_bus_publishing_on_success():
    """Verify that SUCCESS publishes to incident.verified."""
    async def _test():
        bus = EventBus()
        verified_events = []
        bus.subscribe("incident.verified", lambda ev: verified_events.append(ev))

        agent = VerifierAgent(event_bus=bus)
        agent.start()

        v_input = VerifierInput(
            correlation_id="corr-v1",
            incident_id="INC-v1",
            plan_id="PLAN-V1",
            execution_status="SUCCESS",
            metric_name="latency_ms",
            before_value=850.0,
            after_value=120.0,
        )

        await bus.publish("incident.executed", v_input)

        assert len(verified_events) == 1
        res: VerifierOutput = verified_events[0]
        assert res.status == "SUCCESS"
        assert res.metric == "latency_ms"
        assert res.before == 850.0
        assert res.after == 120.0

        agent.stop()

    asyncio.run(_test())


def test_event_bus_publishing_on_failure():
    """Verify that FAILED publishes to incident.verification_failed."""
    async def _test():
        bus = EventBus()
        failed_events = []
        bus.subscribe("incident.verification_failed", lambda ev: failed_events.append(ev))

        agent = VerifierAgent(event_bus=bus)
        agent.start()

        v_input = VerifierInput(
            correlation_id="corr-v2",
            incident_id="INC-v2",
            plan_id="PLAN-V2",
            execution_status="SUCCESS",
            metric_name="latency_ms",
            before_value=850.0,
            after_value=820.0,  # Still bad
        )

        await bus.publish("incident.executed", v_input)

        assert len(failed_events) == 1
        res: VerifierOutput = failed_events[0]
        assert res.status == "FAILED"
        assert res.verification_passed is False

        agent.stop()

    asyncio.run(_test())
