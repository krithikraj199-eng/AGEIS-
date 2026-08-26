"""
OpenTelemetry Setup and Tracing Instrumentation for AEGIS Ω.
Provides unified distributed trace context, span creation, and persistent trace export.
"""

from datetime import datetime, timezone
from contextlib import contextmanager
import functools
import logging
import time
from typing import Any, Dict, Generator, List, Optional

from runtime.config import get_settings
from .trace_store import SpanRecord, trace_store

logger = logging.getLogger(__name__)

_is_otel_initialized = False
_otel_tracer = None


def setup_telemetry(service_name: Optional[str] = None) -> None:
    """Initialize OpenTelemetry TracerProvider and Exporters."""
    global _is_otel_initialized, _otel_tracer
    if _is_otel_initialized:
        return

    settings = get_settings()
    svc_name = service_name or settings.otel_service_name

    try:
        import importlib
        trace = importlib.import_module("opentelemetry.trace")
        resources = importlib.import_module("opentelemetry.sdk.resources")
        sdk_trace = importlib.import_module("opentelemetry.sdk.trace")
        sdk_export = importlib.import_module("opentelemetry.sdk.trace.export")

        Resource = getattr(resources, "Resource")
        TracerProvider = getattr(sdk_trace, "TracerProvider")
        SimpleSpanProcessor = getattr(sdk_export, "SimpleSpanProcessor")
        ConsoleSpanExporter = getattr(sdk_export, "ConsoleSpanExporter")

        resource = Resource.create({
            "service.name": svc_name,
            "environment": settings.environment,
            "system.architecture": "AEGIS-OMEGA-12-STAGE",
        })
        provider = TracerProvider(resource=resource)

        # In dev/debug, output spans to console or local collector
        if settings.debug:
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(provider)
        _otel_tracer = trace.get_tracer("aegis.engine")
        _is_otel_initialized = True
        logger.info(f"OpenTelemetry TracerProvider initialized for service: {svc_name}")
    except (ImportError, ModuleNotFoundError, Exception) as e:
        logger.warning(f"OpenTelemetry setup fallback: {e}")
        _is_otel_initialized = True


def get_tracer(name: str = "aegis.engine") -> Any:
    """Retrieve an OpenTelemetry tracer instance."""
    global _otel_tracer
    if _otel_tracer is not None:
        return _otel_tracer
    try:
        import importlib
        trace = importlib.import_module("opentelemetry.trace")
        _otel_tracer = trace.get_tracer(name)
        return _otel_tracer
    except (ImportError, ModuleNotFoundError, Exception):
        return _MockTracer(name)


class _MockSpan:
    """Mock span for fallback tracing."""
    def __init__(self, name: str):
        self.name = name
        self.attributes: Dict[str, Any] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_exception(self, exception: Exception) -> None:
        pass


class _MockTracer:
    """Mock tracer."""
    def __init__(self, name: str):
        self.name = name

    def start_as_current_span(self, name: str, **kwargs):
        return _MockSpan(name)


@contextmanager
def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    incident_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> Generator[Any, None, None]:
    """
    Context manager for creating OpenTelemetry spans with persistent trace recording.
    """
    tracer = get_tracer()
    attrs = dict(attributes or {})
    if incident_id:
        attrs["incident_id"] = incident_id
    if agent_id:
        attrs["agent_id"] = agent_id

    start_time = time.perf_counter()
    ts_iso = datetime.now(timezone.utc).isoformat()
    status = "SUCCESS"
    summary = attrs.get("summary", f"{name} executed")

    class _SpanWrapper:
        def __init__(self, inner):
            self._inner = inner
        def __getattr__(self, name):
            return getattr(self._inner, name)
        def set_attribute(self, k, v):
            attrs[k] = v
            if hasattr(self._inner, "set_attribute"):
                self._inner.set_attribute(k, str(v))

    with tracer.start_as_current_span(name) as raw_span:
        span = _SpanWrapper(raw_span)
        for k, v in attrs.items():
            if hasattr(raw_span, "set_attribute"):
                raw_span.set_attribute(k, str(v))
        try:
            yield span
        except Exception as e:
            status = "FAILED"
            summary = f"{name} failed: {e}"
            if hasattr(raw_span, "record_exception"):
                raw_span.record_exception(e)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            final_inc_id = attrs.get("incident_id") or incident_id or ""
            rec = SpanRecord(
                incident_id=final_inc_id,
                agent_id=attrs.get("agent_id") or agent_id or name,
                span_name=name,
                status=status,
                summary=attrs.get("summary", summary),
                timestamp=ts_iso,
                duration_ms=round(elapsed_ms, 2),
                attributes=attrs,
            )
            trace_store.record_span(rec)


@contextmanager
def trace_agent_span(
    agent_name: str,
    incident_id: str,
    correlation_id: Optional[str] = None,
    summary: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
) -> Generator[Any, None, None]:
    """
    Specialized context manager for recording agent execution spans across all 13 pipeline stages:
    { incident_id, agent_id, timestamp, status, summary, correlation_id }
    """
    attrs = dict(attributes or {})
    attrs["incident_id"] = incident_id
    attrs["agent_id"] = agent_name
    if correlation_id:
        attrs["correlation_id"] = correlation_id
    if summary:
        attrs["summary"] = summary

    with trace_span(
        name=f"agent.{agent_name.lower()}",
        attributes=attrs,
        incident_id=incident_id,
        agent_id=agent_name,
    ) as span:
        yield span


def record_pipeline_stage_span(
    agent_id: str,
    incident_id: str,
    status: str,
    summary: str,
    attributes: Optional[Dict[str, Any]] = None,
) -> SpanRecord:
    """
    Directly record a discrete pipeline stage milestone span into trace store and OpenTelemetry.
    """
    ts_iso = datetime.now(timezone.utc).isoformat()
    attrs = dict(attributes or {})
    attrs["incident_id"] = incident_id
    attrs["agent_id"] = agent_id
    attrs["status"] = status
    attrs["summary"] = summary

    rec = SpanRecord(
        incident_id=incident_id,
        agent_id=agent_id,
        span_name=f"agent.{agent_id.lower()}",
        status=status,
        summary=summary,
        timestamp=ts_iso,
        attributes=attrs,
    )
    trace_store.record_span(rec)
    return rec
