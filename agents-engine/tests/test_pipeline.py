"""
End-to-End Tests for AEGIS Ω 12-Agent Resilience Pipeline.
Proves that mock incidents travel through all 12 stages sequentially without schema errors.
"""

import asyncio
from runtime.event_bus import EventBus
from runtime.main import AgentPipeline
from mocks.event_generator import (
    EventType,
    Severity,
    generate_event,
    generate_cascading_failure,
)


def test_single_incident_full_12_stage_pipeline():
    """Verify that a single incident travels through all 12 agent stages successfully."""
    async def _test():
        bus = EventBus()
        pipeline = AgentPipeline(event_bus=bus)
        pipeline.start()

        event = generate_event(
            asset_id="DATABASE-01",
            event_type=EventType.DATABASE_TIMEOUT,
            severity=Severity.CRITICAL,
        )

        summary = await pipeline.execute_incident(event, timeout_seconds=5.0)

        assert summary.success is True
        assert summary.final_status == "RESOLVED"
        assert len(summary.stages_completed) >= 12

        expected_stages = [
            "Sentinel",
            "Investigator",
            "Evidence",
            "Dependency",
            "Security",
            "Root Cause",
            "Planner",
            "Counterfactual",
            "Risk",
            "Executor",
            "Verifier",
            "Recovery",
            "Memory",
        ]
        assert summary.stages_completed == expected_stages

        # Verify outputs at key stages
        outputs = summary.stage_outputs
        assert outputs["Sentinel"]["asset_id"] == "DATABASE-01"
        assert outputs["Evidence"]["cryptographic_hash"] is not None
        assert outputs["Dependency"]["blast_radius_score"] > 0
        assert outputs["Security"]["security_clearance"] is True
        assert outputs["Root Cause"]["primary_failure_cause"] is not None
        assert outputs["Planner"]["action_steps"] is not None
        assert len(outputs["Planner"]["action_steps"]) > 0
        assert outputs["Counterfactual"]["simulation_passed"] is True
        assert outputs["Risk"]["is_approved"] is True
        assert outputs["Executor"]["execution_status"] == "SUCCESS"
        assert outputs["Verifier"]["verification_passed"] is True
        assert outputs["Recovery"]["final_status"] == "RESOLVED"

        pipeline.stop()

    asyncio.run(_test())


def test_cascading_failure_all_events_through_pipeline():
    """Verify that all events in a cascading failure chain travel through all stages."""
    async def _test():
        bus = EventBus()
        pipeline = AgentPipeline(event_bus=bus)
        pipeline.start()

        cascade_events = generate_cascading_failure()
        assert len(cascade_events) == 4

        for ev in cascade_events:
            summary = await pipeline.execute_incident(ev, timeout_seconds=5.0)
            assert summary.success is True
            assert summary.final_status == "RESOLVED"
            assert len(summary.stages_completed) >= 12

        pipeline.stop()

    asyncio.run(_test())


def test_agents_are_decoupled_and_use_only_eventbus():
    """Verify that agents hold no direct references to other agents."""
    bus = EventBus()
    pipeline = AgentPipeline(event_bus=bus)

    for agent in pipeline.agents:
        # Agent must only reference EventBus, not other agent instances
        assert hasattr(agent, "event_bus")
        for other_agent in pipeline.agents:
            if agent is not other_agent:
                assert not hasattr(agent, other_agent.name.lower().replace(" ", "_"))
