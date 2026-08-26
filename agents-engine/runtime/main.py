"""
AEGIS Ω — 12-Stage Multi-Agent Resilience Pipeline.
Wired via EventBus:
Sentinel -> Investigator -> Evidence -> Dependency -> Security -> Root Cause ->
Planner -> Counterfactual -> Risk -> Executor -> Verifier -> Recovery.
"""

import argparse
import asyncio
import logging
import sys
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

# Ensure agents-engine is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from runtime.event_bus import EventBus, get_event_bus
from runtime.config import get_settings
from observability.telemetry import setup_telemetry
from mocks.event_generator import (
    EventType,
    Severity,
    SystemEvent,
    generate_event,
    generate_cascading_failure,
)
from agents import (
    SentinelAgent,
    InvestigatorAgent,
    EvidenceAgent,
    DependencyAgent,
    SecurityAgent,
    RootCauseAgent,
    PlannerAgent,
    CounterfactualAgent,
    RiskAgent,
    ExecutorAgent,
    VerifierAgent,
    RecoveryAgent,
)

logger = logging.getLogger(__name__)


class PipelineExecutionSummary(BaseModel):
    """Execution summary of an incident traversing the 12 agent stages."""
    correlation_id: str
    incident_id: str
    success: bool
    stages_completed: List[str]
    stage_outputs: Dict[str, Any]
    final_status: str
    elapsed_seconds: float


class AgentPipeline:
    """
    AEGIS Ω 12-Agent Resilience Pipeline.
    Initializes all 12 agents and wires them strictly through the in-memory EventBus.
    No agent directly calls or references another agent.
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus or get_event_bus()

        # Instantiate all 12 agents sharing the decoupled EventBus
        self.sentinel = SentinelAgent(event_bus=self.event_bus)
        self.investigator = InvestigatorAgent(event_bus=self.event_bus)
        self.evidence = EvidenceAgent(event_bus=self.event_bus)
        self.dependency = DependencyAgent(event_bus=self.event_bus)
        self.security = SecurityAgent(event_bus=self.event_bus)
        self.root_cause = RootCauseAgent(event_bus=self.event_bus)
        self.planner = PlannerAgent(event_bus=self.event_bus)
        self.counterfactual = CounterfactualAgent(event_bus=self.event_bus)
        self.risk = RiskAgent(event_bus=self.event_bus)
        self.executor = ExecutorAgent(event_bus=self.event_bus)
        self.verifier = VerifierAgent(event_bus=self.event_bus)
        self.recovery = RecoveryAgent(event_bus=self.event_bus)

        self.agents = [
            self.sentinel,
            self.investigator,
            self.evidence,
            self.dependency,
            self.security,
            self.root_cause,
            self.planner,
            self.counterfactual,
            self.risk,
            self.executor,
            self.verifier,
            self.recovery,
        ]

    def start(self) -> None:
        """Start all 12 agents by subscribing each to its inbound EventBus topic."""
        for agent in self.agents:
            agent.start()
        logger.info("All 12 AEGIS Omega agents started and listening on EventBus.")

    def stop(self) -> None:
        """Stop all 12 agents."""
        for agent in self.agents:
            agent.stop()
        logger.info("All 12 AEGIS Omega agents stopped.")

    async def execute_incident(
        self,
        event: SystemEvent,
        timeout_seconds: float = 10.0,
        on_stage_complete: Optional[Any] = None,
    ) -> PipelineExecutionSummary:
        """
        Feed a raw telemetry event into the pipeline and wait for the incident
        to travel through all 12 stages to resolution.
        """
        start_time = asyncio.get_running_loop().time()
        correlation_id = event.correlation_id

        stages_completed: List[str] = []
        stage_outputs: Dict[str, Any] = {}
        resolution_future: asyncio.Future = asyncio.get_running_loop().create_future()

        # Track progress across all 12 topics
        topic_agent_map = {
            "incident.triage": "Sentinel",
            "incident.diagnostics": "Investigator",
            "incident.evidence": "Evidence",
            "incident.topology": "Dependency",
            "incident.security_cleared": "Security",
            "incident.root_cause": "Root Cause",
            "incident.plan_proposed": "Planner",
            "incident.simulation_passed": "Counterfactual",
            "incident.risk_approved": "Risk",
            "incident.executed": "Executor",
            "incident.verified": "Verifier",
            "incident.resolved": "Recovery",
        }

        async def stage_tracker(topic: str, output_event: Any):
            cid = getattr(output_event, "correlation_id", None)
            if cid == correlation_id:
                agent_name = topic_agent_map.get(topic, topic)
                stages_completed.append(agent_name)
                stage_outputs[agent_name] = output_event.model_dump() if hasattr(output_event, "model_dump") else output_event

                if on_stage_complete:
                    if asyncio.iscoroutinefunction(on_stage_complete):
                        await on_stage_complete(agent_name, output_event)
                    else:
                        on_stage_complete(agent_name, output_event)

                if topic == "incident.resolved" and not resolution_future.done():
                    resolution_future.set_result(output_event)

        # Attach tracker handlers
        handlers = []
        for topic in topic_agent_map.keys():
            handler = lambda ev, t=topic: asyncio.create_task(stage_tracker(t, ev))
            self.event_bus.subscribe(topic, handler)
            handlers.append((topic, handler))

        try:
            # Publish initial raw telemetry event
            await self.event_bus.publish("telemetry.raw", event)

            # Wait until recovery finishes or timeout
            await asyncio.wait_for(resolution_future, timeout=timeout_seconds)
            final_event = resolution_future.result()
            final_status = getattr(final_event, "final_status", "RESOLVED")
            incident_id = getattr(final_event, "incident_id", "UNKNOWN")
            success = True

            # Record Memory Bank Stage span to complete the 13-stage trace
            try:
                from observability.telemetry import record_pipeline_stage_span
                record_pipeline_stage_span(
                    agent_id="Memory",
                    incident_id=incident_id,
                    status="SUCCESS",
                    summary="Memory stored episode record & extracted patterns",
                    attributes={"correlation_id": correlation_id},
                )
                stages_completed.append("Memory")
            except Exception as e:
                logger.warning(f"Memory span recording fallback: {e}")

        except asyncio.TimeoutError:
            final_status = "TIMEOUT"
            incident_id = f"INC-{correlation_id[:8]}"
            success = False

        finally:
            # Clean up tracker listeners
            for topic, handler in handlers:
                self.event_bus.unsubscribe(topic, handler)

        elapsed = asyncio.get_running_loop().time() - start_time

        return PipelineExecutionSummary(
            correlation_id=correlation_id,
            incident_id=incident_id,
            success=success,
            stages_completed=stages_completed,
            stage_outputs=stage_outputs,
            final_status=final_status,
            elapsed_seconds=round(elapsed, 4),
        )


# ---------------------------------------------------------------------------
# CLI Pipeline Runner
# ---------------------------------------------------------------------------
async def async_main():
    """Main CLI execution routine."""
    parser = argparse.ArgumentParser(
        description="AEGIS Ω — 12-Stage Agent Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        choices=["single", "cascade"],
        default="single",
        help="Incident scenario to execute (default: single)",
    )
    parser.add_argument(
        "--event-type",
        default="DATABASE_TIMEOUT",
        help="Event type for single scenario (default: DATABASE_TIMEOUT)",
    )
    parser.add_argument(
        "--asset-id",
        default="DATABASE-01",
        help="Asset ID for single scenario (default: DATABASE-01)",
    )

    args = parser.parse_args()

    setup_telemetry()
    bus = get_event_bus()
    pipeline = AgentPipeline(event_bus=bus)
    pipeline.start()

    print("=" * 78)
    print("  AEGIS OMEGA -- 12-Stage Multi-Agent Resilience Pipeline")
    print("=" * 78)

    async def log_stage(agent_name: str, data: Any):
        print(f"  [>] Stage: {agent_name:<16} completed successfully.")

    if args.scenario == "single":
        event = generate_event(
            asset_id=args.asset_id,
            event_type=EventType(args.event_type),
            severity=Severity.CRITICAL,
        )
        print(f"[*] Dispatching Incident: [{event.asset_id}] {event.event_type.value} (CID: {event.correlation_id})")
        print("[*] Traversing all 12 agent stages...")

        summary = await pipeline.execute_incident(event, on_stage_complete=log_stage)

        print("\n" + "=" * 78)
        print("  PIPELINE EXECUTION SUMMARY")
        print("=" * 78)
        print(f"  Incident ID:       {summary.incident_id}")
        print(f"  Correlation ID:    {summary.correlation_id}")
        print(f"  Stages Completed:  {len(summary.stages_completed)} / 12 ({', '.join(summary.stages_completed)})")
        print(f"  Final Status:      {summary.final_status}")
        print(f"  Elapsed Time:      {summary.elapsed_seconds}s")
        print("=" * 78)

    elif args.scenario == "cascade":
        print(f"[*] Dispatching Cascading Failure Chain (DATABASE-01 -> AUTH-01 -> API-01 -> PORTAL-01)")
        events = generate_cascading_failure()
        for idx, ev in enumerate(events, 1):
            print(f"\n[{idx}/4] Processing Cascade Event: [{ev.asset_id}] {ev.event_type.value}")
            summary = await pipeline.execute_incident(ev, on_stage_complete=log_stage)
            print(f"  [+] Incident {summary.incident_id} resolved with status: {summary.final_status}")

    pipeline.stop()


def main():
    """Sync entry point."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
