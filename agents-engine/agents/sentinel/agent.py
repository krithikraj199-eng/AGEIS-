"""
Sentinel Agent for AEGIS Ω.
Continuously monitors incoming telemetry events and classifies status as
NORMAL, WARNING, ANOMALY, or CRITICAL.
Performs deterministic threshold checks before invoking Gemini for semantic correlation.
"""

import asyncio
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Protocol, Union
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from agents.sentinel.config import SentinelThresholds
from runtime.event_bus import EventBus
from runtime.llm import get_gemini_client, GeminiClientWrapper
from observability.telemetry import trace_span

logger = logging.getLogger(__name__)


class SentinelStatus(str, Enum):
    """System health status determined by Sentinel Agent."""
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    ANOMALY = "ANOMALY"
    CRITICAL = "CRITICAL"


class SentinelInput(BaseModel):
    """Input event schema for Sentinel Agent (compatible with SystemEvent)."""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    asset_id: str
    event_type: str
    severity: str = "INFO"
    metrics: Dict[str, Any] = Field(default_factory=dict)
    source: str = "telemetry_collector"
    correlation_id: str


class SentinelOutput(BaseModel):
    """
    Required output schema for Sentinel Agent:
    { incident_id, status, triggering_events, summary, timestamp }
    """
    incident_id: str
    status: SentinelStatus
    triggering_events: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str
    asset_id: str


class GeminiCorrelatorProtocol(Protocol):
    """Clean interface for Gemini semantic event correlation to allow mocking."""

    async def correlate_and_summarize(
        self,
        events: List[Dict[str, Any]],
        correlation_id: str,
    ) -> str:
        """Perform semantic correlation and generate a human-readable explanation."""
        ...


class GeminiSemanticCorrelator:
    """
    Gemini API client wrapper for semantic multi-event correlation.
    Only called when multiple correlated anomalies are detected within a time window.
    Never receives raw continuous metric streams.
    """

    def __init__(self, llm_wrapper: Optional[GeminiClientWrapper] = None):
        self.llm_wrapper = llm_wrapper or get_gemini_client()
        self.call_count = 0  # Useful for testing / telemetry

    async def correlate_and_summarize(
        self,
        events: List[Dict[str, Any]],
        correlation_id: str,
    ) -> str:
        """
        Send a concise aggregated summary of correlated anomalies to Gemini
        for human-readable root cause & impact synthesis.
        """
        self.call_count += 1

        # Format concise structured summary of the anomaly signals
        event_lines = []
        for idx, ev in enumerate(events, 1):
            asset = ev.get("asset_id", "unknown")
            etype = ev.get("event_type", "unknown")
            sev = ev.get("severity", "unknown")
            metrics = ev.get("metrics", {})
            event_lines.append(f"  {idx}. Asset: {asset} | Type: {etype} | Severity: {sev} | Key Metrics: {metrics}")

        events_block = "\n".join(event_lines)

        from governance.guardrails import wrap_prompt_with_data_guardrails
        prompt, _ = wrap_prompt_with_data_guardrails(
            system_role=(
                f"You are the AEGIS Ω Sentinel AI. Analyze the following {len(events)} correlated anomalies "
                f"detected under Correlation ID: {correlation_id}. Provide a concise 1-2 sentence human-readable "
                "explanation describing the apparent failure cascade and primary operational impact."
            ),
            untrusted_content=events_block,
            agent_scope="Sentinel",
        )

        # If LLM API key is configured, call Gemini
        if self.llm_wrapper and self.llm_wrapper.is_configured:
            try:
                client = self.llm_wrapper.get_client()
                # Async completion or thread execution
                if hasattr(client, "aio") and hasattr(client.aio, "models"):
                    response = await client.aio.models.generate_content(
                        model=self.llm_wrapper.model_name,
                        contents=prompt,
                    )
                    return response.text.strip()
                elif hasattr(client, "generate_content"):
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(
                        None, lambda: client.generate_content(prompt)
                    )
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Gemini correlation call failed, falling back to deterministic synthesis: {e}")

        # Deterministic semantic synthesis fallback
        assets = [ev.get("asset_id", "unknown") for ev in events]
        root_asset = assets[0] if assets else "unknown"
        return (
            f"Correlated failure cascade detected across {len(events)} assets ({' -> '.join(assets)}). "
            f"Primary disruption initiated on {root_asset} and propagated downstream."
        )


class SentinelAgent(BaseAgent[SentinelInput, SentinelOutput]):
    """
    Sentinel Agent:
    - Continuously ingests incoming events from the event bus.
    - Evaluates configurable deterministic thresholds in Python.
    - Maintains a sliding correlation window for correlated multi-signal events.
    - Invokes Gemini ONLY when multiple related signals occur.
    - Publishes incident triage events to 'incident.triage' for WARNING and above.
    """

    name = "Sentinel"
    description = "Monitors telemetry streams, detects threshold breaches, and performs semantic correlation."
    inbound_topic = "telemetry.raw"
    outbound_topic = "incident.triage"
    input_schema = SentinelInput
    output_schema = SentinelOutput

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        thresholds: Optional[SentinelThresholds] = None,
        correlator: Optional[GeminiCorrelatorProtocol] = None,
    ):
        super().__init__(event_bus=event_bus)
        self.thresholds = thresholds or SentinelThresholds()
        self.correlator = correlator or GeminiSemanticCorrelator()
        # Sliding correlation window buffer: Dict[correlation_id, List[dict]]
        self._correlation_buffer: Dict[str, List[Dict[str, Any]]] = {}

    def _check_deterministic_thresholds(self, event: SentinelInput) -> SentinelStatus:
        """
        Evaluate deterministic threshold conditions using pure Python logic.
        Never calls Gemini.
        """
        etype = event.event_type.upper()
        metrics = event.metrics or {}
        severity = event.severity.upper()

        # 1. Critical event types
        if etype in ["SERVICE_CRASH", "DATABASE_TIMEOUT"]:
            return SentinelStatus.CRITICAL
        if severity == "CRITICAL":
            return SentinelStatus.CRITICAL

        # 2. Security Alerts
        if etype == "SECURITY_ALERT" or severity == "HIGH":
            return SentinelStatus.ANOMALY

        # 3. CPU Threshold Check (> 90%)
        cpu_pct = metrics.get("cpu_utilization_pct") or metrics.get("cpu_pct") or metrics.get("cpu")
        if cpu_pct is not None and float(cpu_pct) >= self.thresholds.cpu_threshold_pct:
            return SentinelStatus.WARNING

        # 4. Memory Threshold Check (> 95%)
        mem_pct = metrics.get("memory_used_pct") or metrics.get("memory_pct") or metrics.get("mem")
        if mem_pct is not None and float(mem_pct) >= self.thresholds.memory_threshold_pct:
            return SentinelStatus.WARNING

        # 5. Disk Threshold Check (> 95%)
        disk_pct = metrics.get("disk_used_pct") or metrics.get("disk_pct")
        if disk_pct is not None and float(disk_pct) >= self.thresholds.disk_threshold_pct:
            return SentinelStatus.ANOMALY

        # 6. Latency Threshold Check
        latency = (
            metrics.get("p99_latency_ms")
            or metrics.get("query_latency_ms")
            or metrics.get("auth_latency_ms")
            or metrics.get("latency_ms")
        )
        if latency is not None and float(latency) >= self.thresholds.latency_threshold_ms:
            return SentinelStatus.ANOMALY

        # 7. Error Rate Threshold Check
        error_rate = (
            metrics.get("error_rate_pct")
            or metrics.get("failed_auth_rate_pct")
            or metrics.get("http_5xx_rate_pct")
            or metrics.get("user_facing_error_rate_pct")
        )
        if error_rate is not None and float(error_rate) >= self.thresholds.error_rate_threshold_pct:
            return SentinelStatus.ANOMALY

        # 8. Warning event types
        if etype in ["MEMORY_WARNING", "NETWORK_LATENCY", "LOGIN_FAILURE", "DISK_FULL"]:
            return SentinelStatus.WARNING

        return SentinelStatus.NORMAL

    def _prune_and_buffer_event(self, event: SentinelInput) -> List[Dict[str, Any]]:
        """
        Buffer the event under its correlation_id within the correlation window.
        Removes expired events older than correlation_window_seconds.
        """
        cid = event.correlation_id
        now_ts = datetime.now(timezone.utc).timestamp()

        if cid not in self._correlation_buffer:
            self._correlation_buffer[cid] = []

        # Parse event timestamp if available
        try:
            event_ts = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")).timestamp()
        except Exception:
            event_ts = now_ts

        event_record = {
            "timestamp": event.timestamp,
            "recorded_at": event_ts,
            "asset_id": event.asset_id,
            "event_type": event.event_type,
            "severity": event.severity,
            "metrics": event.metrics,
            "source": event.source,
            "correlation_id": event.correlation_id,
        }
        self._correlation_buffer[cid].append(event_record)

        # Prune events older than the window
        cutoff = now_ts - self.thresholds.correlation_window_seconds
        self._correlation_buffer[cid] = [
            e for e in self._correlation_buffer[cid] if e.get("recorded_at", now_ts) >= cutoff
        ]

        return self._correlation_buffer[cid]

    async def process(self, input_data: SentinelInput) -> SentinelOutput:
        """
        Process an incoming telemetry event:
        1. Evaluate deterministic threshold logic.
        2. Buffer under correlation_id.
        3. If multiple correlated events occur in window -> invoke Gemini.
        4. If isolated event -> do NOT invoke Gemini, generate deterministic summary.
        5. Return SentinelOutput conforming to the exact schema.
        """
        correlation_id = input_data.correlation_id
        incident_id = f"INC-{correlation_id}"

        # Step 1: Deterministic threshold check
        status = self._check_deterministic_thresholds(input_data)

        # Step 2: Buffer event for multi-signal correlation
        buffered_events = self._prune_and_buffer_event(input_data)
        num_correlated = len(buffered_events)

        summary: str

        # Step 3 & 4: Multi-signal correlation vs isolated breach
        if num_correlated >= self.thresholds.min_events_for_gemini and status != SentinelStatus.NORMAL:
            # Multiple related signals occurred within window -> CALL GEMINI
            summary = await self.correlator.correlate_and_summarize(
                events=buffered_events,
                correlation_id=correlation_id,
            )
            # Escalate status if multiple severe anomalies are correlated
            if any(e.get("severity") == "CRITICAL" or e.get("event_type") in ["SERVICE_CRASH", "DATABASE_TIMEOUT"] for e in buffered_events):
                status = SentinelStatus.CRITICAL
            elif status == SentinelStatus.WARNING:
                status = SentinelStatus.ANOMALY
        else:
            # Isolated breach or normal event -> NEVER CALL GEMINI
            if status == SentinelStatus.NORMAL:
                summary = f"Telemetry normal for asset '{input_data.asset_id}'. No threshold breaches detected."
            else:
                metrics_str = ", ".join(f"{k}={v}" for k, v in input_data.metrics.items()) if input_data.metrics else "no metrics"
                summary = (
                    f"Deterministic threshold breach on asset '{input_data.asset_id}': "
                    f"event_type={input_data.event_type}, severity={input_data.severity}, metrics=[{metrics_str}]."
                )

        output = SentinelOutput(
            incident_id=incident_id,
            status=status,
            triggering_events=buffered_events,
            summary=summary,
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id=correlation_id,
            asset_id=input_data.asset_id,
        )

        return output

    async def handle_event(self, raw_event: Any) -> Optional[SentinelOutput]:
        """
        Event handler invoked by the EventBus when an event arrives on inbound_topic.
        Validates input schema, traces execution via OpenTelemetry, performs deterministic
        and conditional semantic checks, and publishes to outbound_topic ONLY for WARNING and above.
        """
        correlation_id = getattr(raw_event, "correlation_id", "unknown")
        if isinstance(raw_event, dict):
            correlation_id = raw_event.get("correlation_id", "unknown")

        inc_id = f"INC-{correlation_id}"

        span_attrs = {
            "agent_id": "Sentinel",
            "agent.name": self.name,
            "agent.inbound_topic": self.inbound_topic,
            "agent.outbound_topic": self.outbound_topic or "none",
            "correlation_id": correlation_id,
            "incident_id": inc_id,
            "summary": "Sentinel detected anomaly and evaluated thresholds",
        }

        with trace_span(
            name="agent.sentinel",
            attributes=span_attrs,
            incident_id=inc_id,
            agent_id="Sentinel",
        ) as span:
            try:
                if isinstance(raw_event, self.input_schema):
                    input_data = raw_event
                elif isinstance(raw_event, BaseModel):
                    input_data = self.input_schema.model_validate(raw_event.model_dump())
                elif isinstance(raw_event, dict):
                    input_data = self.input_schema.model_validate(raw_event)
                else:
                    logger.error(f"[{self.name}] Unsupported event payload format: {type(raw_event)}")
                    return None

                output_data: SentinelOutput = await self.process(input_data)

                # Set incident_id and updated summary on span
                span.set_attribute("incident_id", output_data.incident_id)
                if output_data.status != SentinelStatus.NORMAL:
                    span.set_attribute("summary", f"Sentinel detected {output_data.status.value} anomaly on {output_data.asset_id}")
                else:
                    span.set_attribute("summary", f"Sentinel evaluated normal telemetry for {output_data.asset_id}")

                # Rule 9: WARNING, ANOMALY, and CRITICAL must publish an Incident event for Investigator.
                # NORMAL events do not publish to incident.triage.
                if self.outbound_topic and output_data.status != SentinelStatus.NORMAL:
                    await self.event_bus.publish(self.outbound_topic, output_data)
                    logger.debug(f"[{self.name}] Published incident triage event to '{self.outbound_topic}'")

                return output_data

            except Exception as e:
                logger.exception(f"[{self.name}] Error during event processing: {e}")
                if hasattr(span, "record_exception"):
                    span.record_exception(e)
                raise
