"""
AEGIS Ω — Main FastAPI Application

Exposes the Digital World, AI Intelligence, and Governance
layers through a REST + WebSocket API.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import HOST, PORT, DEBUG
from .digital_world.state import DigitalWorldState
from .digital_world.models import Severity, IncidentStatus, IncidentType
from .agents.pipeline import AegisAgentRuntime


# ═══════════════════════════════════════════════════════════
# GLOBAL WORLD STATE
# ═══════════════════════════════════════════════════════════

world: DigitalWorldState | None = None
runtime: AegisAgentRuntime | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the digital world simulation."""
    global world, runtime
    world = DigitalWorldState(sim_speed=60.0)
    runtime = AegisAgentRuntime(world)
    world.intelligence_runtime = runtime
    await world.start(tick_interval=2.0)
    await runtime.start()
    print("[AEGIS] Digital World started")
    print(f"[AEGIS] {world.institution.get_asset_count()} assets loaded")
    print(f"[AEGIS] {world.dep_graph.get_graph_summary()['total_edges']} dependencies")
    yield
    await runtime.stop()
    await world.stop()
    print("[AEGIS] Digital World stopped")


# ═══════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="AEGIS Ω",
    description="Autonomous Institutional Intelligence & Self-Healing Operating System",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════

class InjectScenarioRequest(BaseModel):
    scenario_id: str

class InjectStressRequest(BaseModel):
    asset_id: str
    stress_type: str
    intensity: float = 0.7

class RecoverRequest(BaseModel):
    failure_id: str
    recovery_pct: float = 0.8

class TimeControlRequest(BaseModel):
    action: str  # "pause", "resume", "set_speed", "advance_hours", "advance_days"
    value: float = 1.0

class CreateIncidentRequest(BaseModel):
    title: str
    description: str
    severity: str = "medium"
    affected_assets: List[str] = Field(default_factory=list)

class DemoRunRequest(BaseModel):
    scenario_id: str = "database_crisis"
    force_first_failure: bool = True
    wait_for_completion: bool = False

class PredictionActionRequest(BaseModel):
    prediction_id: str

class PreventionRequest(BaseModel):
    prediction_id: str
    wait_for_completion: bool = False


# ═══════════════════════════════════════════════════════════
# ROUTES — WORLD STATE
# ═══════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "AEGIS Ω",
        "version": "2.0.0",
        "simulation": bool(world and world.running),
        "intelligence": runtime.status()["status"] if runtime else "starting",
        "ai_mode": runtime.reasoner.status["mode"] if runtime else "starting",
    }


@app.get("/api/world/state")
async def get_world_state():
    """Get the current world state summary."""
    return world.get_world_state().model_dump()


@app.get("/api/world/time")
async def get_time():
    """Get current simulation time."""
    return world.time_engine.get_state()


@app.post("/api/world/time")
async def control_time(req: TimeControlRequest):
    """Control simulation time."""
    if req.action == "pause":
        world.time_engine.pause()
    elif req.action == "resume":
        world.time_engine.resume()
    elif req.action == "set_speed":
        world.time_engine.set_speed(req.value)
    elif req.action == "advance_hours":
        world.time_engine.advance_hours(req.value)
    elif req.action == "advance_days":
        world.time_engine.advance_days(int(req.value))
    else:
        raise HTTPException(400, f"Unknown action: {req.action}")
    return world.time_engine.get_state()


# ═══════════════════════════════════════════════════════════
# ROUTES — ASSETS
# ═══════════════════════════════════════════════════════════

@app.get("/api/assets")
async def get_all_assets(
    asset_type: str = None,
    department: str = None,
    status: str = None,
):
    """Get all assets with optional filters."""
    assets = world.get_all_assets_summary()
    if asset_type:
        assets = [a for a in assets if a["type"] == asset_type]
    if department:
        assets = [a for a in assets if a["department"] == department]
    if status:
        assets = [a for a in assets if a["status"] == status]
    return {"assets": assets, "total": len(assets)}


@app.get("/api/assets/{asset_id}")
async def get_asset_detail(asset_id: str):
    """Get detailed asset information."""
    detail = world.get_asset_details(asset_id)
    if not detail:
        raise HTTPException(404, f"Asset {asset_id} not found")
    return detail


@app.get("/api/assets/{asset_id}/metrics/history")
async def get_asset_metrics_history(asset_id: str, last_n: int = 50):
    """Get metric history for an asset."""
    return {
        "asset_id": asset_id,
        "history": world.metrics_engine.get_history(asset_id, last_n),
    }


@app.get("/api/assets/{asset_id}/metrics/trend")
async def get_asset_metric_trend(asset_id: str, metric: str = "cpu_percent"):
    """Get trend analysis for a specific metric."""
    trend = world.metrics_engine.get_metric_trend(asset_id, metric)
    if not trend:
        return {"asset_id": asset_id, "metric": metric, "trend": None}
    return {"asset_id": asset_id, **trend}


# ═══════════════════════════════════════════════════════════
# ROUTES — DEPENDENCY GRAPH
# ═══════════════════════════════════════════════════════════

@app.get("/api/graph/summary")
async def get_graph_summary():
    """Get dependency graph summary."""
    return world.dep_graph.get_graph_summary()


@app.get("/api/graph/visualization")
async def get_graph_visualization():
    """Get graph data for frontend visualization."""
    return world.dep_graph.get_graph_for_visualization()


@app.get("/api/graph/blast-radius/{asset_id}")
async def get_blast_radius(asset_id: str):
    """Calculate blast radius for an asset failure."""
    return world.dep_graph.get_blast_radius(asset_id)


@app.get("/api/graph/critical-assets")
async def get_critical_assets(top_n: int = 15):
    """Get the most critical assets by impact analysis."""
    return world.dep_graph.find_critical_assets(top_n)


@app.get("/api/graph/cascade-path")
async def get_cascade_path(source: str, target: str):
    """Find the failure propagation path between two assets."""
    path = world.dep_graph.find_cascading_path(source, target)
    return {"source": source, "target": target, "path": path}


@app.get("/api/graph/spof")
async def get_single_points_of_failure():
    """Get single points of failure."""
    return {"spof": world.dep_graph.get_single_points_of_failure()}


# ═══════════════════════════════════════════════════════════
# ROUTES — EVENTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/events")
async def get_recent_events(count: int = 50):
    """Get recent events."""
    events = world.event_engine.get_recent_events(count)
    return {
        "events": [e.model_dump() for e in events],
        "total": len(events),
    }


@app.get("/api/events/stats")
async def get_event_stats():
    """Get event statistics."""
    return world.event_engine.get_event_stats()


@app.get("/api/events/asset/{asset_id}")
async def get_asset_events(asset_id: str, count: int = 50):
    """Get events for a specific asset."""
    events = world.event_engine.get_events_for_asset(asset_id, count)
    return {"events": [e.model_dump() for e in events]}


# ═══════════════════════════════════════════════════════════
# ROUTES — CHAOS LAB
# ═══════════════════════════════════════════════════════════

@app.get("/api/chaos/scenarios")
async def get_chaos_scenarios():
    """Get available chaos scenarios."""
    return {"scenarios": world.chaos_engine.get_available_scenarios()}


@app.post("/api/chaos/inject")
async def inject_chaos_scenario(req: InjectScenarioRequest):
    """Inject a failure scenario."""
    result = world.chaos_engine.inject_scenario(req.scenario_id)
    if not result:
        raise HTTPException(400, f"Unknown scenario: {req.scenario_id}")
    incident = next(
        (item for item in world.incidents.values() if item.metadata.get("failure_id") == result["failure_id"]),
        None,
    )
    return {**result, "incident_id": incident.incident_id if incident else None}


@app.post("/api/chaos/stress")
async def inject_stress(req: InjectStressRequest):
    """Inject stress on a single asset."""
    result = world.chaos_engine.inject_stress(
        req.asset_id, req.stress_type, req.intensity
    )
    if not result:
        raise HTTPException(404, f"Asset {req.asset_id} not found")
    return result


@app.post("/api/chaos/recover")
async def recover_failure(req: RecoverRequest):
    """Recover from a failure."""
    success = world.chaos_engine.recover_failure(req.failure_id, req.recovery_pct)
    if not success:
        raise HTTPException(404, f"Failure {req.failure_id} not found or inactive")
    return {"status": "recovered", "failure_id": req.failure_id}


@app.post("/api/chaos/recover-all")
async def recover_all():
    """Recover from all active failures."""
    world.chaos_engine.recover_all()
    return {"status": "all_recovered"}


@app.get("/api/chaos/active")
async def get_active_failures():
    """Get all active failures."""
    return {"failures": world.chaos_engine.get_active_failures()}


@app.get("/api/chaos/history")
async def get_failure_history(last_n: int = 50):
    """Get failure injection history."""
    return {"history": world.chaos_engine.get_failure_history(last_n)}


# ═══════════════════════════════════════════════════════════
# ROUTES — INCIDENTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/incidents")
async def get_incidents(active_only: bool = False, last_n: int = 50):
    """Get incidents."""
    if active_only:
        return {"incidents": world.get_active_incidents()}
    return {"incidents": world.get_all_incidents(last_n)}


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Get a specific incident."""
    incident = world.incidents.get(incident_id)
    if not incident:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return incident.model_dump()


@app.post("/api/incidents")
async def create_incident(req: CreateIncidentRequest):
    """Manually create an incident."""
    incident = world.create_incident(
        title=req.title,
        description=req.description,
        severity=Severity(req.severity),
        affected_assets=req.affected_assets,
    )
    return incident.model_dump()


# ═══════════════════════════════════════════════════════════
# ROUTES — INTELLIGENCE, GOVERNANCE, MEMORY, OBSERVABILITY
# ═══════════════════════════════════════════════════════════

@app.get("/api/system/status")
async def get_system_status():
    return runtime.status()


@app.get("/api/agents")
async def get_agent_registry():
    return runtime.registry.summary()


@app.get("/api/traces")
async def get_agent_traces(limit: int = 100, incident_id: str | None = None):
    return {"traces": runtime.traces.recent(limit, incident_id)}


@app.get("/api/audit")
async def get_audit_log(limit: int = 100):
    return {"entries": runtime.audit.recent(limit)}


@app.get("/api/memory")
async def get_memory(limit: int = 50):
    return {
        "summary": runtime.memory.summary(),
        "episodes": runtime.memory.recent(limit),
        "procedures": runtime.memory.procedures(limit),
    }


@app.get("/api/predictions")
async def get_predictions(active_only: bool = True):
    return {"predictions": runtime.predictor.list(active_only)}


@app.post("/api/predictions/scan")
async def scan_predictions():
    return {"created": runtime.predictor.scan(), "predictions": runtime.predictor.list()}


@app.post("/api/predictions/acknowledge")
async def acknowledge_prediction(req: PredictionActionRequest):
    if not runtime.predictor.acknowledge(req.prediction_id):
        raise HTTPException(404, f"Prediction {req.prediction_id} not found")
    return {"status": "acknowledged", "prediction_id": req.prediction_id}


@app.post("/api/predictions/prevent")
async def prevent_prediction(req: PreventionRequest):
    incident = runtime.prevent_prediction(req.prediction_id)
    if not incident:
        raise HTTPException(404, f"Active prediction {req.prediction_id} not found")
    if req.wait_for_completion:
        await runtime.wait_for_incident(incident.incident_id, timeout=30)
    return {
        "status": incident.status.value,
        "prediction_id": req.prediction_id,
        "incident": incident.model_dump(mode="json"),
    }


@app.post("/api/incidents/{incident_id}/retry")
async def retry_incident(incident_id: str):
    incident = world.incidents.get(incident_id)
    if not incident:
        raise HTTPException(404, f"Incident {incident_id} not found")
    current = runtime._tasks.get(incident_id)
    if current and not current.done():
        raise HTTPException(409, "Incident pipeline is already running")
    incident.status = IncidentStatus.DETECTED
    runtime._tasks.pop(incident_id, None)
    runtime.on_incident(incident)
    return {"status": "retry_started", "incident_id": incident_id}


@app.post("/api/demo/run")
async def run_demo(req: DemoRunRequest):
    """Run the complete detect→diagnose→fail→rollback→recover→learn story."""
    if req.force_first_failure:
        runtime.arm_demo_failure()
    result = world.chaos_engine.inject_scenario(req.scenario_id)
    if not result:
        raise HTTPException(400, f"Unknown scenario: {req.scenario_id}")
    incident = next(
        (item for item in world.incidents.values() if item.metadata.get("failure_id") == result["failure_id"]),
        None,
    )
    if not incident:
        raise HTTPException(500, "Scenario was injected but incident correlation failed")
    if req.wait_for_completion:
        await runtime.wait_for_incident(incident.incident_id, timeout=30)
    return {
        "status": "completed" if incident.status.value in {"resolved", "failed", "escalated"} else "running",
        "failure_id": result["failure_id"],
        "incident": incident.model_dump(mode="json"),
    }


# ═══════════════════════════════════════════════════════════
# WEBSOCKET — REAL-TIME UPDATES
# ═══════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time world state updates via WebSocket."""
    await websocket.accept()

    async def send_update(data: dict):
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    world.subscribe_ws(send_update)
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        world.unsubscribe_ws(send_update)
    except Exception:
        world.unsubscribe_ws(send_update)


# ═══════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
    )
