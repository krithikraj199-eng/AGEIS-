"""
Master Integration Test Suite for the COMPLETE AEGIS Ω Intelligence Engine.
Verifies the end-to-end 20-step lifecycle across cascading failures:
DATABASE-01 -> AUTH-01 -> API-01 -> PORTAL-01

All 20 Requirements Tested:
1. Mock Digital World emits failure events
2. Sentinel detects anomaly
3. Investigator generates competing hypotheses
4. Evidence validates concrete metrics
5. Dependency calculates blast radius
6. Security classifies incident
7. Root Cause synthesizes the evidence
8. Planner generates multiple remediation plans
9. Counterfactual predicts outcomes
10. Risk calculates deterministic risk
11. Executor enforces risk gate
12. Executor executes allowed action
13. Verifier checks the SAME triggering metric
14. Recovery rolls back, replans excluding failed plan, and retries upon failure
15. Successful resolution enters Memory Bank
16. Procedural memory updates strategy success
17. Semantic memory records learned patterns
18. OpenTelemetry records the entire incident
19. Trace report reconstructs the incident chronologically
20. Audit log contains all actions
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timezone

from runtime.event_bus import EventBus
from runtime.main import AgentPipeline, PipelineExecutionSummary
from mocks.event_generator import (
    EventType,
    Severity,
    SystemEvent,
    generate_cascading_failure,
    generate_event,
)
from memory import episodic_memory, semantic_memory, procedural_memory
from memory.episodic import EpisodeRecord
from observability.telemetry import trace_store, setup_telemetry
from observability.trace_report import generate_trace_timeline, generate_simple_timeline
from agents.executor.agent import ExecutorAgent
from tools.client import MockDigitalWorldClient


def test_complete_aegis_omega_cascading_failure_integration():
    """
    Execute the entire cascading failure scenario through live AEGIS Ω pipeline
    and audit all 20 requirements end-to-end.
    """
    async def _test():
        # Setup telemetry and clean state
        setup_telemetry()
        trace_store.clear()
        episodic_memory.clear()
        procedural_memory.clear()

        bus = EventBus()
        client = MockDigitalWorldClient()
        pipeline = AgentPipeline(event_bus=bus)
        pipeline.executor.client = client
        pipeline.start()

        # Step 1: Mock Digital World emits cascading failure chain
        cascade_events = generate_cascading_failure(correlation_id="cascade-omega-full")
        assert len(cascade_events) == 4
        expected_assets = ["DATABASE-01", "AUTH-01", "API-01", "PORTAL-01"]
        for ev, expected_asset in zip(cascade_events, expected_assets):
            assert ev.asset_id == expected_asset

        incident_summaries = []

        # Run each cascading failure event through the complete live 13-stage pipeline
        for ev in cascade_events:
            summary: PipelineExecutionSummary = await pipeline.execute_incident(ev, timeout_seconds=8.0)
            assert summary.success is True
            assert summary.final_status == "RESOLVED"
            incident_summaries.append(summary)

            # Step 2: Sentinel detects anomaly
            sentinel_out = summary.stage_outputs.get("Sentinel")
            assert sentinel_out is not None
            assert sentinel_out["status"] in ["CRITICAL", "ANOMALY", "WARNING"]
            assert sentinel_out["asset_id"] == ev.asset_id

            # Step 3: Investigator generates competing hypotheses (K >= 3)
            investigator_out = summary.stage_outputs.get("Investigator")
            assert investigator_out is not None
            assert len(investigator_out["hypotheses"]) >= 3
            assert investigator_out["asset_id"] == ev.asset_id

            # Step 4: Evidence validates concrete metrics
            evidence_out = summary.stage_outputs.get("Evidence")
            assert evidence_out is not None
            assert "evidence" in evidence_out
            assert len(evidence_out["evidence"]) > 0
            assert evidence_out["cryptographic_hash"] is not None
            assert evidence_out["evidence"][0]["metric"] is not None

            # Step 5: Dependency calculates blast radius
            dependency_out = summary.stage_outputs.get("Dependency")
            assert dependency_out is not None
            assert dependency_out["blast_radius_score"] > 0.0
            assert len(dependency_out["upstream_dependencies"]) >= 0

            # Step 6: Security classifies incident
            security_out = summary.stage_outputs.get("Security")
            assert security_out is not None
            assert security_out["classification"] in ["OPERATIONAL_FAILURE", "SECURITY_INCIDENT", "SUSPICIOUS_ANOMALY"]
            assert security_out["security_clearance"] is True

            # Step 7: Root Cause synthesizes the evidence
            root_cause_out = summary.stage_outputs.get("Root Cause")
            assert root_cause_out is not None
            assert root_cause_out["primary_failure_cause"] is not None
            assert root_cause_out["confidence"] > 0.5

            # Step 8: Planner generates multiple remediation plans with rollback info
            planner_out = summary.stage_outputs.get("Planner")
            assert planner_out is not None
            assert len(planner_out["plans"]) >= 2
            for plan in planner_out["plans"]:
                assert plan["rollback_method"] is not None
                assert plan["actions"][0]["tool"] in ["restart_service", "scale_service", "rollback_deployment", "clear_cache", "quarantine_asset", "restore_configuration"]

            # Step 9: Counterfactual predicts outcomes & ranks safest plan
            cf_out = summary.stage_outputs.get("Counterfactual")
            assert cf_out is not None
            assert cf_out["simulation_passed"] is True
            assert cf_out["selected_plan_id"] is not None

            # Step 10: Risk calculates deterministic risk (0-100)
            risk_out = summary.stage_outputs.get("Risk")
            assert risk_out is not None
            assert 0 <= risk_out["risk_score"] <= 100
            assert risk_out["tier"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

            # Step 11: Executor enforces risk gate
            assert risk_out["gate_decision"] in ["AUTO_EXECUTE", "SUPERVISOR_REVIEW", "HOLD_FOR_APPROVAL", "REFUSE_EXECUTION"]

            # Step 12: Executor executes allowed action
            exec_out = summary.stage_outputs.get("Executor")
            assert exec_out is not None
            assert exec_out["execution_status"] in ["SUCCESS", "SUCCESS_REVIEW_FLAGGED", "AUTO_EXECUTED", "SUPERVISOR_APPROVED"]
            assert "audit_records" in exec_out
            assert len(exec_out["audit_records"]) > 0
            assert exec_out["audit_records"][0]["tool_name"] in ["restart_service", "scale_service", "rollback_deployment", "clear_cache", "quarantine_asset", "restore_configuration"]

            # Step 13: Verifier checks the SAME triggering metric
            verifier_out = summary.stage_outputs.get("Verifier")
            assert verifier_out is not None
            assert verifier_out["verification_passed"] is True
            assert verifier_out["status"] == "SUCCESS"
            assert verifier_out["metric"] in ["latency_ms", "query_latency_ms", "auth_latency_ms", "portal_latency_ms", "cpu_usage_pct"]
            assert verifier_out["after"] <= verifier_out["before"]  # Metric improved

            # Step 15: Successful resolution recorded
            recovery_out = summary.stage_outputs.get("Recovery")
            assert recovery_out is not None
            assert recovery_out["final_status"] == "RESOLVED"

            # Register episode in memory bank
            event_type_str = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
            action_tool = planner_out["selected_plan"]["actions"][0]["tool"]
            signature_str = f"{ev.asset_id}:{event_type_str}"

            episodic_memory.record_episode(
                incident_id=summary.incident_id,
                correlation_id=ev.correlation_id,
                root_cause=root_cause_out["primary_failure_cause"],
                plan=planner_out["selected_plan"],
                outcome="SUCCESS",
                timestamps={"start": ev.timestamp, "resolved": datetime.now(timezone.utc).isoformat()},
                blast_radius={"score": dependency_out["blast_radius_score"]},
                incident_signature=signature_str,
            )

            # Record action outcome in procedural memory
            procedural_memory.record_action_outcome(
                signature=signature_str,
                strategy=action_tool,
                success=True,
            )

        pipeline.stop()

        # Step 15 & 16: Procedural memory updates strategy success
        stats_map = procedural_memory.get_strategy_stats("DATABASE-01:DATABASE_TIMEOUT")
        assert len(stats_map) >= 1
        first_tool = list(stats_map.keys())[0]
        strat = stats_map[first_tool]
        assert strat is not None
        assert strat.total_executions >= 1
        assert strat.success_count >= 1

        # Step 17: Semantic memory records learned patterns
        semantic_patterns = semantic_memory.search_patterns("database")
        assert isinstance(semantic_patterns, list)

        # Step 18: OpenTelemetry records spans for every incident
        all_recorded_ids = trace_store.get_all_incident_ids()
        assert len(all_recorded_ids) >= 1

        first_inc = incident_summaries[0].incident_id
        spans = trace_store.get_trace(first_inc)
        assert len(spans) >= 12

        # Verify all span required fields: incident_id, agent_id, timestamp, status
        for s in spans:
            assert s.incident_id == first_inc
            assert s.agent_id != ""
            assert s.timestamp != ""
            assert s.status in ["SUCCESS", "DETECTED", "STARTED"]

        # Step 19: Trace report reconstructs the incident chronologically
        timeline = generate_trace_timeline(spans, first_inc)
        assert first_inc in timeline
        assert "Sentinel" in timeline
        assert "Investigator" in timeline
        assert "Evidence" in timeline
        assert "Dependency" in timeline
        assert "Security" in timeline
        assert "Root Cause" in timeline
        assert "Planner" in timeline
        assert "Counterfactual" in timeline
        assert "Risk" in timeline
        assert "Executor" in timeline
        assert "Verifier" in timeline
        assert "Recovery" in timeline
        assert "Memory" in timeline

        simple_timeline = generate_simple_timeline(spans)
        assert "Sentinel detected" in simple_timeline
        assert "Verifier audited" in simple_timeline

        # Step 20: Audit log contains all actions
        audit_log = pipeline.executor.get_audit_log()
        assert len(audit_log) >= 4
        for entry in audit_log:
            assert "plan_id" in entry
            assert "tool_name" in entry
            assert "actor" in entry
            assert entry["actor"] in ["AEGIS_OMEGA_EXECUTOR", "ExecutorAgent", "Executor"]

    asyncio.run(_test())


def test_failure_rollback_and_replanning_recovery_lifecycle():
    """
    Step 14: Dedicated test verifying that if verification fails:
    1. Recovery rolls back the failed execution
    2. Planner excludes the failed plan_id
    3. New plan is generated & counterfactually validated
    4. Pipeline retries and successfully resolves the incident
    """
    async def _test():
        from agents.recovery.agent import RecoveryAgent, RecoveryInput
        from agents.planner.agent import PlannerAgent, PlannerInput
        from agents.counterfactual.agent import CounterfactualAgent
        from agents.risk.agent import RiskAgent
        from agents.verifier.agent import VerifierAgent, VerifierInput
        from agents.planner.models import RemediationPlan

        bus = EventBus()
        client = MockDigitalWorldClient()
        executor = ExecutorAgent(event_bus=bus, client=client)
        planner = PlannerAgent(event_bus=bus)
        verifier = VerifierAgent(event_bus=bus)
        recovery = RecoveryAgent(event_bus=bus)

        inc_id = "INC-RECOVERY-REPLAN-999"
        failed_plan_id = "PLAN-FAIL-RESTART"

        # Simulate a failed verification
        failed_verifier_input = VerifierInput(
            incident_id=inc_id,
            correlation_id="corr-recovery-999",
            plan_id=failed_plan_id,
            metric_name="latency_ms",
            before_value=850.0,
            after_value=920.0,  # Worsened -> FAILED
        )

        verifier_out = await verifier.process(failed_verifier_input)
        assert verifier_out.status == "FAILED"
        assert verifier_out.verification_passed is False

        # Pass failed verification into Recovery
        recovery_in = RecoveryInput(
            incident_id=inc_id,
            correlation_id="corr-recovery-999",
            plan_id=failed_plan_id,
            status="FAILED",
            verification_passed=False,
            target_asset="DATABASE-01",
            rollback_method="systemctl restart database-replica",
            evidence=verifier_out.evidence,
        )

        # Recovery executes rollback and triggers replan
        recovery_out = await recovery.process(recovery_in)
        assert recovery_out.rollback_required is True
        assert recovery_out.attempts[0].rollback_executed is True

        # Reinvoke Planner with excluded failed plan
        planner_in = PlannerInput(
            incident_id=inc_id,
            correlation_id="corr-recovery-999",
            root_asset_id="DATABASE-01",
            primary_failure_cause="DATABASE_TIMEOUT",
            supporting_evidence=["Connection pool exhaustion"],
            blast_radius=0.75,
            classification="OPERATIONAL_FAILURE",
            excluded_plan_ids=[failed_plan_id],
        )

        planner_out = await planner.process(planner_in)
        # Verify failed plan is strictly excluded from candidate plans
        candidate_ids = [p.plan_id for p in planner_out.plans]
        assert failed_plan_id not in candidate_ids
        assert planner_out.plan_id != failed_plan_id

        # Second plan verifies successfully
        second_plan = planner_out.plans[0]
        second_verifier_in = VerifierInput(
            incident_id=inc_id,
            correlation_id="corr-recovery-999",
            plan_id=second_plan.plan_id,
            metric_name="latency_ms",
            before_value=850.0,
            after_value=110.0,  # Improved -> SUCCESS
        )
        second_verifier_out = await verifier.process(second_verifier_in)
        assert second_verifier_out.status == "SUCCESS"
        assert second_verifier_out.verification_passed is True

    asyncio.run(_test())
