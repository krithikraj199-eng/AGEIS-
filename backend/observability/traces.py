"""Lightweight OpenTelemetry-shaped trace records for every agent action."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable, Dict, List, TypeVar

from ..digital_world.models import AgentTrace

T = TypeVar("T")


class TraceStore:
    def __init__(self, max_entries: int = 5000) -> None:
        self._traces: deque[AgentTrace] = deque(maxlen=max_entries)

    def run(
        self,
        agent_id: str,
        agent_name: str,
        action: str,
        incident_id: str | None,
        fn: Callable[[], T],
        input_data: Dict[str, Any] | None = None,
    ) -> T:
        started = perf_counter()
        status = "success"
        output: Any = None
        try:
            output = fn()
            return output
        except Exception as exc:
            status = "error"
            output = {"error": str(exc)}
            raise
        finally:
            serializable_output = output if isinstance(output, dict) else {"result": str(output)}
            self._traces.append(
                AgentTrace(
                    incident_id=incident_id,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    action=action,
                    input_data=input_data,
                    output_data=serializable_output,
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    status=status,
                    timestamp=datetime.now(timezone.utc),
                )
            )

    def add(self, trace: AgentTrace) -> None:
        self._traces.append(trace)

    def recent(self, limit: int = 100, incident_id: str | None = None) -> List[Dict[str, Any]]:
        traces = list(self._traces)
        if incident_id:
            traces = [trace for trace in traces if trace.incident_id == incident_id]
        return [trace.model_dump(mode="json") for trace in traces[-max(1, min(limit, 500)) :]][::-1]

