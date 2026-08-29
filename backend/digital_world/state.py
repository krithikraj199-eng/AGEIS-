"""
AEGIS Ω — Digital World State Manager

The central orchestrator that ties together:
- Institution (assets)
- Dependency Graph
- Metrics Engine
- Event Engine
- Time Engine
- Chaos Engine

This is the single entry point the rest of the system uses
to interact with the digital world.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .models import (
    Asset, AssetStatus, Event, Incident, IncidentStatus,
    IncidentType, Severity, WorldState
)
from .institution import InstitutionBuilder
from .dependencies import DependencyGraph
from .metrics import MetricsEngine
from .events import EventEngine
from .time_engine import TimeEngine
from .chaos_engine import ChaosEngine


class DigitalWorldState:
    """
    The complete state of the digital world.
    One instance exists for the lifetime of the application.
    """

    def __init__(self, sim_speed: float = 60.0):
        # 1. Build the institution
        self.institution = InstitutionBuilder()
        self.assets = self.institution.get_all_assets()

        # 2. Build dependency graph
        self.dep_graph = DependencyGraph()
        self.dep_graph.build_from_assets(self.assets)

        # 3. Engines
        self.metrics_engine = MetricsEngine()
        self.event_engine = EventEngine(self.metrics_engine)
        self.time_engine = TimeEngine(speed=sim_speed)
        self.chaos_engine = ChaosEngine(
            self.metrics_engine, self.event_engine,
            self.dep_graph, self.assets
        )

        # 4. Incidents
        self.incidents: Dict[str, Incident] = {}
        self.incident_counter = 0

        # 5. Register chaos → incident callback
        self.chaos_engine.set_incident_callback(self._on_chaos_incident)

        # 6. Simulation state
        self.running = False
        self._tick_task: Optional[asyncio.Task] = None

        # 7. WebSocket subscribers
        self._ws_subscribers: List[Callable] = []

        # 8. Intelligence runtime hooks (registered by the application lifespan)
        self._incident_listeners: List[Callable[[Incident], None]] = []
        self.intelligence_runtime: Any = None

    # ══════════════════════════════════════════════════════
    # SIMULATION LOOP
    # ══════════════════════════════════════════════════════

    async def start(self, tick_interval: float = 2.0):
        """Start the simulation loop."""
        if self.running:
            return
        self.running = True
        self._tick_task = asyncio.create_task(
            self._simulation_loop(tick_interval)
        )

    async def stop(self):
        """Stop the simulation loop."""
        self.running = False
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None

    async def _simulation_loop(self, interval: float):
        """Main simulation tick."""
        while self.running:
            try:
                # Advance time
                self.time_engine.tick(interval)

                # Generate events from metric drifts
                events = self.event_engine.generate_metric_events(
                    self.assets, self.time_engine.sim_hour
                )

                # Track day stats
                for _ in events:
                    self.time_engine.record_day_event()

                # Update dependency graph statuses
                for aid, asset in self.assets.items():
                    self.dep_graph.update_node_status(
                        aid, asset.status.value
                    )

                # Broadcast state to WebSocket clients
                await self._broadcast_state()

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[WorldState] Simulation error: {e}")
                await asyncio.sleep(interval)

    # ══════════════════════════════════════════════════════
    # INCIDENT MANAGEMENT
    # ══════════════════════════════════════════════════════

    def create_incident(self, title: str, description: str,
                        severity: Severity,
                        affected_assets: List[str],
                        triggering_events: List[str] = None,
                        incident_type: IncidentType = IncidentType.REACTIVE) -> Incident:
        """Create a new incident."""
        self.incident_counter += 1
        incident = Incident(
            incident_id=f"INC-{self.incident_counter:05d}",
            title=title,
            description=description,
            severity=severity,
            incident_type=incident_type,
            affected_assets=affected_assets,
            triggering_events=triggering_events or [],
            timeline=[{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "system",
                "action": "incident_created",
                "details": f"Incident created: {title}",
            }],
        )
        self.incidents[incident.incident_id] = incident
        self.time_engine.record_day_incident()
        for listener in self._incident_listeners[:]:
            try:
                listener(incident)
            except Exception as exc:
                print(f"[WorldState] Incident listener error: {exc}")
        return incident

    def add_incident_listener(self, callback: Callable[[Incident], None]):
        """Subscribe an intelligence runtime to newly created incidents."""
        if callback not in self._incident_listeners:
            self._incident_listeners.append(callback)

    def remove_incident_listener(self, callback: Callable[[Incident], None]):
        self._incident_listeners = [listener for listener in self._incident_listeners if listener != callback]

    def update_incident(self, incident_id: str, **kwargs) -> Optional[Incident]:
        """Update an incident's fields."""
        incident = self.incidents.get(incident_id)
        if not incident:
            return None
        for key, value in kwargs.items():
            if hasattr(incident, key):
                setattr(incident, key, value)
        return incident

    def add_incident_timeline(self, incident_id: str, agent: str,
                              action: str, details: str):
        """Add a timeline entry to an incident."""
        incident = self.incidents.get(incident_id)
        if incident:
            incident.timeline.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": agent,
                "action": action,
                "details": details,
            })

    def _on_chaos_incident(self, failure_record: Dict[str, Any]):
        """Called by ChaosEngine when a scenario is injected."""
        correlated_events = self.event_engine.get_events_by_correlation(
            failure_record.get("correlation_id", "")
        )
        incident = self.create_incident(
            title=failure_record["scenario_name"],
            description=failure_record["description"],
            severity=Severity(failure_record["severity"]),
            affected_assets=failure_record["affected_assets"],
            triggering_events=[event.event_id for event in correlated_events],
            incident_type=IncidentType.REACTIVE,
        )
        incident.metadata.update({
            "failure_id": failure_record.get("failure_id"),
            "scenario_id": failure_record.get("scenario_id"),
            "correlation_id": failure_record.get("correlation_id"),
            "target_asset": failure_record.get("target_asset"),
            "is_security": failure_record.get("is_security", False),
        })

    # ══════════════════════════════════════════════════════
    # QUERIES
    # ══════════════════════════════════════════════════════

    def get_world_state(self) -> WorldState:
        """Get the current state summary."""
        healthy = sum(1 for a in self.assets.values() if a.status == AssetStatus.HEALTHY)
        degraded = sum(1 for a in self.assets.values() if a.status in (AssetStatus.DEGRADED, AssetStatus.WARNING))
        critical = sum(1 for a in self.assets.values() if a.status == AssetStatus.CRITICAL)
        offline = sum(1 for a in self.assets.values() if a.status == AssetStatus.OFFLINE)
        total = len(self.assets)

        active_incidents = sum(
            1 for i in self.incidents.values()
            if i.status not in (IncidentStatus.RESOLVED, IncidentStatus.FAILED)
        )

        health_pct = (healthy / total * 100) if total > 0 else 100

        runtime = self.intelligence_runtime
        return WorldState(
            timestamp=self.time_engine.current_time,
            total_assets=total,
            healthy_assets=healthy,
            degraded_assets=degraded,
            critical_assets=critical,
            offline_assets=offline,
            active_incidents=active_incidents,
            total_events_today=self.event_engine.event_count,
            overall_health_pct=round(health_pct, 1),
            agent_count=len(runtime.registry.list()) if runtime else 0,
            predictions_active=len(runtime.predictor.list()) if runtime else 0,
        )

    def get_asset_details(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed asset info including metrics history and dependencies."""
        asset = self.assets.get(asset_id)
        if not asset:
            return None

        return {
            "asset": asset.model_dump(),
            "metrics_history": self.metrics_engine.get_history(asset_id, 50),
            "dependencies": self.dep_graph.get_direct_dependencies(asset_id),
            "dependents": self.dep_graph.get_direct_dependents(asset_id),
            "blast_radius": self.dep_graph.get_blast_radius(asset_id),
            "recent_events": [
                e.model_dump() for e in
                self.event_engine.get_events_for_asset(asset_id, 20)
            ],
        }

    def get_all_assets_summary(self) -> List[Dict[str, Any]]:
        """Get a compact summary of all assets."""
        return [
            {
                "asset_id": a.asset_id,
                "name": a.name,
                "type": a.asset_type.value,
                "department": a.department.value,
                "status": a.status.value,
                "criticality": a.criticality,
                "cpu": round(a.metrics.cpu_percent, 1),
                "memory": round(a.metrics.memory_percent, 1),
                "disk": round(a.metrics.disk_percent, 1),
                "latency": round(a.metrics.network_latency_ms, 1),
                "error_rate": round(a.metrics.error_rate, 1),
            }
            for a in self.assets.values()
        ]

    def get_active_incidents(self) -> List[Dict[str, Any]]:
        return [
            i.model_dump()
            for i in self.incidents.values()
            if i.status not in (IncidentStatus.RESOLVED, IncidentStatus.FAILED)
        ]

    def get_all_incidents(self, last_n: int = 50) -> List[Dict[str, Any]]:
        incidents = list(self.incidents.values())
        incidents.sort(key=lambda x: x.created_at, reverse=True)
        return [i.model_dump() for i in incidents[:last_n]]

    # ══════════════════════════════════════════════════════
    # WEBSOCKET BROADCAST
    # ══════════════════════════════════════════════════════

    def subscribe_ws(self, callback: Callable):
        self._ws_subscribers.append(callback)

    def unsubscribe_ws(self, callback: Callable):
        self._ws_subscribers = [s for s in self._ws_subscribers if s != callback]

    async def _broadcast_state(self):
        if not self._ws_subscribers:
            return
        state = self.get_world_state()
        data = {
            "type": "world_state",
            "data": state.model_dump(),
            "time": self.time_engine.get_state(),
        }
        for cb in self._ws_subscribers[:]:
            try:
                await cb(data)
            except Exception:
                self._ws_subscribers.remove(cb)
