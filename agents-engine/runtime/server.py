"""
Cloud Run HTTP Server for AEGIS Ω Intelligence Engine.
Provides health endpoints, telemetry ingestion, and Pub/Sub push webhooks.
"""

import base64
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
import uvicorn

from runtime.config import get_settings
from runtime.event_bus import EventBus
from runtime.pubsub_bus import get_pubsub_event_bus
from runtime.main import AgentPipeline, PipelineExecutionSummary
from storage.cloud_sql import get_cloud_sql_storage
from memory.firestore_store import get_firestore_backend
from digital_world.client import get_digital_world_client
from digital_world.models import DigitalWorldEvent
from observability.telemetry import trace_store, setup_telemetry
from observability.trace_report import generate_simple_timeline

logger = logging.getLogger("aegis_server")

# Global pipeline instance
pipeline_instance: Optional[AgentPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI Cloud Run service."""
    global pipeline_instance
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    setup_telemetry()

    # Initialize Pub/Sub event bus and pipeline
    bus = get_pubsub_event_bus()
    dw_client = get_digital_world_client()
    pipeline_instance = AgentPipeline(event_bus=bus)
    pipeline_instance.executor.client = dw_client
    pipeline_instance.start()

    # Initialize Cloud SQL
    cloud_sql = get_cloud_sql_storage()
    await cloud_sql.initialize()

    logger.info(f"AEGIS Ω Intelligence Engine online on port {settings.port}")
    yield
    if pipeline_instance:
        pipeline_instance.stop()
    logger.info("AEGIS Ω Intelligence Engine shutdown completed.")


app = FastAPI(
    title="AEGIS Ω Autonomous Cloud SRE Intelligence Engine",
    description="Autonomous incident detection, multi-hypothesis diagnosis, risk-gated remediation, and closed-loop memory.",
    version="1.0.0",
    lifespan=lifespan,
)


class HealthResponse(BaseModel):
    """Health check response payload."""
    status: str
    service: str
    version: str
    timestamp: str
    environment: str
    components: Dict[str, str]


class IncidentTriggerRequest(BaseModel):
    """Direct incident trigger request payload."""
    asset_id: str
    event_type: str = "DATABASE_TIMEOUT"
    severity: str = "CRITICAL"
    metrics: Dict[str, Any] = Field(default_factory=dict)
    source: str = "http_api"
    correlation_id: Optional[str] = None


class PubSubPushMessage(BaseModel):
    """Google Cloud Pub/Sub Push Subscription wrapper."""
    message: Dict[str, Any]
    subscription: Optional[str] = None


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Service health check endpoint for Cloud Run container liveness and readiness probes.
    """
    settings = get_settings()
    gemini_status = "configured" if settings.gemini_api_key else "not_configured"
    pubsub_status = "active" if settings.enable_gcp_pubsub else "in_memory_fallback"
    cloud_sql_status = "active" if settings.enable_cloud_sql else "in_memory_fallback"
    firestore_status = "active" if settings.enable_firestore else "in_memory_fallback"

    pipeline_active = bool(
        pipeline_instance and any(getattr(a, "_running", False) for a in pipeline_instance.agents)
    )

    return HealthResponse(
        status="healthy",
        service="aegis-omega-intelligence-engine",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        environment=settings.environment,
        components={
            "pipeline": "active" if pipeline_active else "stopped",
            "gemini": gemini_status,
            "pubsub": pubsub_status,
            "cloud_sql": cloud_sql_status,
            "firestore": firestore_status,
            "agents_registered": "13",
        },
    )


@app.get("/", tags=["Info"])
async def root_info():
    """Service metadata and active configuration summary."""
    return {
        "service": "AEGIS Ω Autonomous Intelligence Engine",
        "description": "Multi-agent SRE runtime on Google Cloud Run",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "incident_trigger": "/api/v1/incident",
            "pubsub_push": "/api/v1/pubsub/push",
            "traces": "/api/v1/traces/{incident_id}",
        },
    }


@app.post("/api/v1/incident", tags=["Incidents"])
async def trigger_incident(req: IncidentTriggerRequest):
    """
    Trigger or ingest an incident directly into the 13-stage autonomous pipeline.
    """
    if not pipeline_instance:
        raise HTTPException(status_code=503, detail="Pipeline engine is not initialized.")

    dw_client = get_digital_world_client()
    event = dw_client.generate_event(
        asset_id=req.asset_id,
        event_type=req.event_type,
        severity=req.severity,
        metrics=req.metrics,
        source=req.source,
        correlation_id=req.correlation_id,
    )

    summary: PipelineExecutionSummary = await pipeline_instance.execute_incident(event, timeout_seconds=10.0)

    # Persist incident to Cloud SQL
    cloud_sql = get_cloud_sql_storage()
    await cloud_sql.save_incident({
        "incident_id": summary.incident_id,
        "correlation_id": event.correlation_id,
        "asset_id": event.asset_id,
        "event_type": event.event_type,
        "severity": event.severity,
        "status": summary.final_status,
        "detected_at": event.timestamp,
        "resolved_at": datetime.now(timezone.utc).isoformat() if summary.success else None,
    })

    return {
        "incident_id": summary.incident_id,
        "correlation_id": event.correlation_id,
        "asset_id": event.asset_id,
        "final_status": summary.final_status,
        "success": summary.success,
        "duration_seconds": round(summary.elapsed_seconds, 3),
        "stages_executed": list(summary.stage_outputs.keys()),
    }


@app.post("/api/v1/pubsub/push", tags=["PubSub"])
async def pubsub_push_webhook(envelope: PubSubPushMessage):
    """
    Google Cloud Pub/Sub Push Subscription webhook receiver.
    Decodes base64 Pub/Sub payload and routes through AEGIS Ω pipeline.
    """
    if not envelope.message or "data" not in envelope.message:
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub push message format.")

    try:
        raw_data = base64.b64decode(envelope.message["data"]).decode("utf-8")
        event_dict = json.loads(raw_data)
    except Exception as e:
        logger.error(f"Error decoding Pub/Sub push message: {e}")
        raise HTTPException(status_code=400, detail=f"Cannot decode Pub/Sub data: {e}")

    # Process payload if it represents a system event
    if "asset_id" in event_dict and "event_type" in event_dict and pipeline_instance:
        dw_client = get_digital_world_client()
        ev = dw_client.generate_event(
            asset_id=event_dict["asset_id"],
            event_type=event_dict["event_type"],
            severity=event_dict.get("severity", "CRITICAL"),
            metrics=event_dict.get("metrics", {}),
            source=event_dict.get("source", "pubsub_push"),
            correlation_id=event_dict.get("correlation_id"),
        )
        summary = await pipeline_instance.execute_incident(ev, timeout_seconds=10.0)
        return {"status": "ACK", "incident_id": summary.incident_id, "resolution": summary.final_status}

    return {"status": "ACK", "processed": True}


@app.get("/api/v1/traces/{incident_id}", tags=["Observability"])
async def get_incident_trace(incident_id: str):
    """Retrieve recorded trace timeline for an incident."""
    spans = trace_store.get_trace(incident_id)
    if not spans:
        raise HTTPException(status_code=404, detail=f"No trace found for incident {incident_id}")

    timeline_str = generate_simple_timeline(spans)
    return {
        "incident_id": incident_id,
        "span_count": len(spans),
        "timeline": timeline_str.strip().split("\n"),
        "spans": [s.model_dump() for s in spans],
    }


def start_server():
    """Run uvicorn server directly."""
    settings = get_settings()
    uvicorn.run(
        "runtime.server:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    start_server()
