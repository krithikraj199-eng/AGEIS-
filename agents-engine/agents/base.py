"""
Base Agent Architecture for AEGIS Ω Intelligence Engine.
Provides strongly-typed event-driven processing, OpenTelemetry tracing, and decoupled EventBus integration.
"""

import abc
import logging
from typing import Any, Generic, Optional, Type, TypeVar
from pydantic import BaseModel
from runtime.event_bus import EventBus, get_event_bus
from observability.telemetry import trace_span

logger = logging.getLogger(__name__)

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)


class BaseAgent(Generic[TInput, TOutput], abc.ABC):
    """
    Abstract base class for all AEGIS Ω resilience agents.
    Enforces strict typing, OpenTelemetry spans, and zero direct agent-to-agent coupling.
    """

    name: str
    description: str
    inbound_topic: str
    outbound_topic: Optional[str] = None
    input_schema: Type[TInput]
    output_schema: Type[TOutput]

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus or get_event_bus()
        self._is_active = False

    def start(self) -> None:
        """Register the agent's event handler to the inbound topic."""
        if not self._is_active:
            self.event_bus.subscribe(self.inbound_topic, self.handle_event)
            self._is_active = True
            logger.info(f"Agent '{self.name}' subscribed to topic '{self.inbound_topic}'")

    def stop(self) -> None:
        """Unregister the agent's event handler."""
        if self._is_active:
            self.event_bus.unsubscribe(self.inbound_topic, self.handle_event)
            self._is_active = False
            logger.info(f"Agent '{self.name}' unsubscribed from topic '{self.inbound_topic}'")

    async def handle_event(self, raw_event: Any) -> Optional[TOutput]:
        """
        Event handler invoked by the EventBus when an event arrives on inbound_topic.
        Validates the input schema, traces execution via OpenTelemetry, executes process logic,
        and publishes the output to outbound_topic.
        """
        correlation_id = getattr(raw_event, "correlation_id", "unknown")
        incident_id = getattr(raw_event, "incident_id", "")
        if isinstance(raw_event, dict):
            correlation_id = raw_event.get("correlation_id", "unknown")
            incident_id = raw_event.get("incident_id", "")

        summary_map = {
            "Sentinel": "Sentinel detected anomaly and evaluated thresholds",
            "Investigator": "Investigator gathered context & hypotheses",
            "Evidence": "Evidence generated metric correlation deltas",
            "Dependency": "Dependency calculated blast radius and topology",
            "Security": "Security screened logs and classified incident",
            "Root Cause": "Root Cause diagnosed causal failure",
            "Planner": "Planner formulated candidate remediation plans",
            "Counterfactual": "Counterfactual simulated and ranked safest plan",
            "Risk": "Risk evaluated safety score and gate authorization",
            "Executor": "Executor executed authorized action steps",
            "Verifier": "Verifier audited post-remediation health telemetry",
            "Recovery": "Recovery evaluated resolution & replanning state",
            "Prediction": "Prediction anticipated impending threshold breach",
        }
        summary_text = summary_map.get(self.name, f"{self.name} completed successfully")

        span_attrs = {
            "agent_id": self.name,
            "agent.name": self.name,
            "agent.inbound_topic": self.inbound_topic,
            "agent.outbound_topic": self.outbound_topic or "none",
            "correlation_id": correlation_id,
            "incident_id": incident_id,
            "summary": summary_text,
        }

        with trace_span(
            name=f"agent.{self.name.lower()}",
            attributes=span_attrs,
            incident_id=incident_id,
            agent_id=self.name,
        ) as span:
            try:
                # Validate input using Pydantic schema
                if isinstance(raw_event, self.input_schema):
                    input_data = raw_event
                elif isinstance(raw_event, BaseModel):
                    input_data = self.input_schema.model_validate(raw_event.model_dump())
                elif isinstance(raw_event, dict):
                    input_data = self.input_schema.model_validate(raw_event)
                else:
                    logger.error(f"[{self.name}] Unsupported event payload format: {type(raw_event)}")
                    return None

                # Execute agent processing logic
                output_data: TOutput = await self.process(input_data)

                # Ensure output strictly adheres to output_schema
                if not isinstance(output_data, self.output_schema):
                    output_data = self.output_schema.model_validate(output_data)

                # Update span attributes from output if incident_id was created during process
                out_inc = getattr(output_data, "incident_id", None)
                if out_inc and not incident_id:
                    span.set_attribute("incident_id", str(out_inc))

                # Emit output event to the outbound bus topic
                if self.outbound_topic:
                    await self.event_bus.publish(self.outbound_topic, output_data)
                    logger.debug(f"[{self.name}] Published output to '{self.outbound_topic}'")

                return output_data

            except Exception as e:
                logger.exception(f"[{self.name}] Error during event processing: {e}")
                if hasattr(span, "record_exception"):
                    span.record_exception(e)
                raise

    @abc.abstractmethod
    async def process(self, input_data: TInput) -> TOutput:
        """Core agent logic. Must be implemented by each subclass."""
        raise NotImplementedError
