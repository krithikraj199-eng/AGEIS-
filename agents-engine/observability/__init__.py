"""
Observability Package for AEGIS Ω Intelligence Engine.
Provides OpenTelemetry tracing and metrics instrumentation.
"""

from .telemetry import get_tracer, setup_telemetry, trace_span

__all__ = [
    "get_tracer",
    "setup_telemetry",
    "trace_span",
]
