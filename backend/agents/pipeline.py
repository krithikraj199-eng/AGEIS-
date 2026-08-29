"""End-to-end autonomous monitoring, diagnosis, remediation, and learning pipeline."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..config import PROJECT_DIR
from ..digital_world.metrics import THRESHOLDS
from ..digital_world.models import (
    Event,
    Incident,
    IncidentStatus,
    SecurityClassification,
)
from ..governance.registry import AgentRegistry, AuditLog
from ..gateway.router import AgentGateway
from ..memory.bank import MemoryBank
from ..observability.traces import TraceStore
from ..tools.remediation import RemediationExecutor, TOOL_RISK
from .gemini import GeminiReasoner
from .predictor.engine import PredictionEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


PLAN_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "database_crisis": [
        {"name": "Scale database capacity", "tool": "scale_service", "recovery": 94, "downtime": 4, "rollback": "remove temporary replica"},
        {"name": "Restart connection pool", "tool": "restart_service", "recovery": 78, "downtime": 18, "rollback": "restore previous process"},
        {"name": "Fail over database", "tool": "failover", "recovery": 98, "downtime": 8, "rollback": "return traffic to primary"},
    ],
    "deployment_regression": [
        {"name": "Clear application cache", "tool": "clear_cache", "recovery": 64, "downtime": 1, "rollback": "warm cache"},
        {"name": "Restart affected service", "tool": "restart_service", "recovery": 80, "downtime": 15, "rollback": "restore prior process"},
        {"name": "Rollback deployment", "tool": "rollback_deployment", "recovery": 97, "downtime": 25, "rollback": "redeploy candidate release"},
    ],
    "security_attack": [
        {"name": "Block malicious source pattern", "tool": "block_ip", "recovery": 92, "downtime": 0, "rollback": "remove temporary deny rule"},
        {"name": "Restart authentication workers", "tool": "restart_service", "recovery": 75, "downtime": 12, "rollback": "restore previous workers"},
        {"name": "Quarantine authentication node", "tool": "quarantine_asset", "recovery": 96, "downtime": 60, "rollback": "release quarantine"},
    ],
    "default": [
        {"name": "Clear transient state", "tool": "clear_cache", "recovery": 68, "downtime": 1, "rollback": "warm caches"},
        {"name": "Restart affected service", "tool": "restart_service", "recovery": 86, "downtime": 15, "rollback": "restore previous process"},
        {"name": "Increase service resources", "tool": "increase_resources", "recovery": 94, "downtime": 3, "rollback": "restore resource limits"},
    ],
}


class AegisAgentRuntime:
    """Coordinates every bounded stage while keeping policy decisions deterministic."""

    def __init__(self, world: Any, *, memory_path: str | None = None, stage_delay: float | None = None) -> None:
        self.world = world
        self.registry = AgentRegistry()
        self.audit = AuditLog()
        self.gateway = AgentGateway(self.registry, self.audit)
        self.traces = TraceStore()
        db_path = memory_path or os.getenv("AEGIS_MEMORY_DB") or str(PROJECT_DIR / "backend" / "database" / "aegis_memory.db")
        self.memory = MemoryBank(db_path)
        self.executor = RemediationExecutor(world, self.registry, self.audit)
        self.predictor = PredictionEngine(world)
        self.reasoner = GeminiReasoner(enabled=os.getenv("AEGIS_AI_ENABLED", "false").lower() == "true")
        self.stage_delay = float(os.getenv("AEGIS_STAGE_DELAY", stage_delay if stage_delay is not None else 0.12))
        self._tasks: Dict[str, asyncio.Task] = {}
        self._prediction_task: asyncio.Task | None = None
        self._event_cooldowns: Dict[str, float] = {}
        self._sentinel_ready_at = 0.0
        self.force_next_failure = False

    async def start(self) -> None:
        self.world.add_incident_listener(self.on_incident)
        self.world.event_engine.subscribe(self.on_event)
        self._sentinel_ready_at = asyncio.get_running_loop().time() + 10.0
        self._prediction_task = asyncio.create_task(self._prediction_loop())
        self.audit.append("system", "runtime_started", details={"agent_count": len(self.registry.list())})

    async def stop(self) -> None:
        if self._prediction_task:
            self._prediction_task.cancel()
            try:
                await self._prediction_task
            except asyncio.CancelledError:
                pass
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        pending = [task for task in self._tasks.values() if not task.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self.world.remove_incident_listener(self.on_incident)
        self.memory.close()

    def arm_demo_failure(self) -> None:
        self.force_next_failure = True

    def on_incident(self, incident: Incident) -> None:
        if incident.incident_id in self._tasks:
            return
        if self.force_next_failure:
            incident.metadata["force_first_failure"] = True
            self.force_next_failure = False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._tasks[incident.incident_id] = loop.create_task(self.process_incident(incident.incident_id))

    def on_event(self, event: Event) -> None:
        if event.source == "chaos_engine" or event.severity.value != "critical":
            return
        asset = self.world.assets.get(event.asset_id)
        if not asset or asset.status.value != "critical":
            return
        loop = asyncio.get_running_loop()
        now = loop.time()
        if now < self._sentinel_ready_at:
            return
        if now - self._event_cooldowns.get(event.asset_id, 0) < 45:
            return
        self._event_cooldowns[event.asset_id] = now
        incident = self.world.create_incident(
            title=f"Sentinel detected {event.event_type.value}",
            description=event.message,
            severity=event.severity,
            affected_assets=[event.asset_id],
            triggering_events=[event.event_id],
        )
        incident.metadata.update({"pattern": event.event_type.value.lower(), "source": "sentinel"})

    async def process_incident(self, incident_id: str) -> None:
        incident = self.world.incidents.get(incident_id)
        if not incident:
            return
        started = utc_now()
        try:
            await self._stage(incident, "sentinel", "Acknowledge anomaly", lambda: self._sentinel(incident))
            investigation = await self._stage(incident, "investigator", "Collect telemetry", lambda: self._investigate(incident))
            evidence = await self._stage(incident, "evidence", "Validate evidence", lambda: self._evidence(incident, investigation))
            dependency = await self._stage(incident, "dependency", "Calculate blast radius", lambda: self._dependency(incident))
            security = await self._stage(incident, "security", "Classify incident", lambda: self._security(incident))
            diagnosis = await self._stage(
                incident, "root_cause", "Correlate root cause",
                lambda: self._root_cause(incident, evidence, dependency, security),
            )
            advisory = await self.reasoner.analyze({"incident": incident.model_dump(mode="json"), "diagnosis": diagnosis})
            if advisory:
                incident.metadata["gemini_advisory"] = advisory
                self._timeline(incident, "root_cause", "gemini_advisory", "Gemini advisory analysis attached; policy engine remains authoritative")
            plans = await self._stage(incident, "planner", "Generate remediation plans", lambda: self._plans(incident, diagnosis))
            plans = await self._stage(incident, "counterfactual", "Simulate candidate futures", lambda: self._counterfactual(plans))
            plans = await self._stage(incident, "risk", "Apply policy and risk gates", lambda: self._risk(plans))
            incident.plans = plans

            eligible = [plan for plan in plans if plan["decision"] == "auto_execute"]
            if not eligible:
                incident.status = IncidentStatus.ESCALATED
                self._timeline(incident, "risk", "escalated", "No plan met autonomous execution policy")
                self.audit.append("risk", "incident_escalated", incident_id=incident.incident_id, outcome="escalated")
                return

            success = False
            selected = None
            verification: Dict[str, Any] = {}
            for attempt, plan in enumerate(eligible[:3], start=1):
                selected = plan
                incident.selected_plan = plan["plan_id"]
                incident.status = IncidentStatus.EXECUTING
                forced = bool(incident.metadata.get("force_first_failure") and attempt == 1)
                execution = await self._stage(
                    incident, "executor", f"Execute {plan['name']}",
                    lambda p=plan, f=forced: self.executor.execute(incident, p, simulate_failure=f),
                )
                execution["attempt"] = attempt
                execution["plan_id"] = plan["plan_id"]
                incident.actions_taken.append(execution)
                incident.status = IncidentStatus.VERIFYING
                verification = await self._stage(
                    incident, "verifier", "Verify success criteria",
                    lambda e=execution: self.executor.verify(incident, e),
                )
                if verification["success"]:
                    success = True
                    break
                incident.status = IncidentStatus.ROLLBACK
                await self._stage(
                    incident, "recovery", "Rollback and replan",
                    lambda a=attempt: {"rolled_back": True, "next_attempt": a + 1, "reason": verification},
                )

            incident.verification_result = verification
            duration = max(0.0, (utc_now() - started).total_seconds())
            if success and selected:
                incident.status = IncidentStatus.RESOLVED
                incident.resolved_at = utc_now()
                incident.resolution_summary = f"{selected['name']} restored service and passed verification"
                self._timeline(incident, "verifier", "resolved", incident.resolution_summary)
                await self._stage(
                    incident, "memory", "Learn from outcome",
                    lambda: self._remember(incident, selected, "success", duration),
                )
            else:
                incident.status = IncidentStatus.FAILED
                incident.resolution_summary = "All policy-approved remediation attempts failed verification"
                if selected:
                    await self._stage(
                        incident, "memory", "Record failed outcome",
                        lambda: self._remember(incident, selected, "failure", duration),
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            incident.status = IncidentStatus.FAILED
            incident.resolution_summary = f"Pipeline error: {exc}"
            self._timeline(incident, "system", "pipeline_failed", str(exc))
            self.audit.append("system", "pipeline_failed", incident_id=incident.incident_id, outcome="failed", details={"error": str(exc)})

    async def _stage(self, incident: Incident, agent_id: str, action: str, fn: Any) -> Any:
        if self.stage_delay:
            await asyncio.sleep(self.stage_delay)
        names = {entry["agent_id"]: entry["name"] for entry in self.registry.list()}
        self.gateway.dispatch(
            sender="system", recipient=agent_id, action=action,
            payload={"incident_id": incident.incident_id, "title": incident.title},
            incident_id=incident.incident_id,
        )
        result = self.traces.run(agent_id, names[agent_id], action, incident.incident_id, fn)
        self._timeline(incident, agent_id, action.lower().replace(" ", "_"), self._stage_details(result))
        self.audit.append(agent_id, action.lower().replace(" ", "_"), incident_id=incident.incident_id)
        return result

    @staticmethod
    def _stage_details(result: Any) -> str:
        if not isinstance(result, dict):
            return str(result)[:180]
        for key in ("summary", "root_cause", "classification", "message", "criteria"):
            if key in result:
                return str(result[key])[:220]
        return ", ".join(f"{key}={value}" for key, value in list(result.items())[:3])[:220]

    def _timeline(self, incident: Incident, agent: str, action: str, details: str) -> None:
        self.world.add_incident_timeline(incident.incident_id, agent, action, details)

    def _sentinel(self, incident: Incident) -> Dict[str, Any]:
        incident.status = IncidentStatus.INVESTIGATING
        return {"summary": f"Correlated {max(1, len(incident.affected_assets))} affected assets into one incident"}

    def _investigate(self, incident: Incident) -> Dict[str, Any]:
        events = []
        for asset_id in incident.affected_assets:
            events.extend(self.world.event_engine.get_events_for_asset(asset_id, 8))
        events.sort(key=lambda event: event.timestamp)
        hypotheses = [
            {"claim": "Primary target resource saturation", "confidence": 0.91},
            {"claim": "Downstream cascade through dependencies", "confidence": 0.82},
            {"claim": "Recent configuration or deployment regression", "confidence": 0.46},
        ]
        incident.hypotheses = hypotheses
        return {"event_count": len(events), "events": [event.model_dump(mode="json") for event in events[-25:]], "hypotheses": hypotheses}

    def _evidence(self, incident: Incident, investigation: Dict[str, Any]) -> Dict[str, Any]:
        evidence = []
        for asset_id in incident.affected_assets:
            asset = self.world.assets.get(asset_id)
            if not asset:
                continue
            for metric, levels in THRESHOLDS.items():
                value = getattr(asset.metrics, metric, None)
                if value is not None and value >= levels["warning"]:
                    evidence.append({
                        "asset_id": asset_id,
                        "metric": metric,
                        "value": round(float(value), 2),
                        "warning": levels["warning"],
                        "supports_root_cause": True,
                    })
        incident.evidence = evidence[:30]
        incident.status = IncidentStatus.EVIDENCE_COLLECTED
        return {"summary": f"Validated {len(evidence)} threshold breaches from raw telemetry", "items": evidence[:30]}

    def _dependency(self, incident: Incident) -> Dict[str, Any]:
        target = incident.metadata.get("target_asset") or (incident.affected_assets[0] if incident.affected_assets else "")
        blast = self.world.dep_graph.get_blast_radius(target) if target in self.world.assets else {"total_affected": 0}
        incident.blast_radius = blast.get("total_affected", 0)
        return {"summary": f"Blast radius includes {incident.blast_radius} transitive dependents", **blast}

    def _security(self, incident: Incident) -> Dict[str, Any]:
        scenario = incident.metadata.get("scenario_id", "")
        classification = (
            SecurityClassification.SECURITY_EVENT
            if incident.metadata.get("is_security") or scenario == "security_attack"
            else SecurityClassification.CONFIGURATION_ERROR
            if scenario == "deployment_regression"
            else SecurityClassification.OPERATIONAL_FAILURE
        )
        incident.security_classification = classification
        return {"classification": classification.value, "confidence": 0.97 if classification != SecurityClassification.UNKNOWN else 0.5}

    def _root_cause(
        self,
        incident: Incident,
        evidence: Dict[str, Any],
        dependency: Dict[str, Any],
        security: Dict[str, Any],
    ) -> Dict[str, Any]:
        target = incident.metadata.get("target_asset") or (incident.affected_assets[0] if incident.affected_assets else "unknown")
        scenario = incident.metadata.get("scenario_id") or incident.metadata.get("pattern") or "resource_saturation"
        root_cause = f"{target} triggered {scenario.replace('_', ' ')} and propagated through dependent services"
        confidence = min(0.99, 0.72 + len(evidence.get("items", [])) * 0.015 + min(0.12, incident.blast_radius * 0.002))
        incident.root_cause = root_cause
        incident.root_cause_confidence = round(confidence * 100, 1)
        incident.status = IncidentStatus.ROOT_CAUSE_IDENTIFIED
        recommendation = self.memory.recommendation(scenario)
        incident.metadata["pattern"] = scenario
        if recommendation:
            incident.metadata["memory_match"] = recommendation
        return {
            "root_cause": root_cause,
            "confidence": incident.root_cause_confidence,
            "classification": security["classification"],
            "historical_recommendation": recommendation,
        }

    def _plans(self, incident: Incident, diagnosis: Dict[str, Any]) -> List[Dict[str, Any]]:
        incident.status = IncidentStatus.PLANNING
        pattern = incident.metadata.get("pattern", "default")
        templates = PLAN_TEMPLATES.get(pattern, PLAN_TEMPLATES["default"])
        recommendation = diagnosis.get("historical_recommendation") or {}
        plans = []
        for index, template in enumerate(templates, start=1):
            memory_boost = 5 if recommendation.get("action") == template["tool"] else 0
            plans.append({
                "plan_id": f"{incident.incident_id}-PLAN-{index}",
                "name": template["name"],
                "description": f"Use {template['tool']} on the scoped simulated assets",
                "actions": [{"tool": template["tool"], "asset_ids": incident.affected_assets, "recovery_pct": 0.98}],
                "expected_recovery_pct": min(100, template["recovery"] + memory_boost),
                "estimated_downtime_seconds": template["downtime"],
                "rollback_method": template["rollback"],
                "memory_boost": memory_boost,
            })
        return plans

    @staticmethod
    def _counterfactual(plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for plan in plans:
            recovery = plan["expected_recovery_pct"]
            downtime = plan["estimated_downtime_seconds"]
            plan["counterfactual_analysis"] = {
                "expected_recovery_pct": recovery,
                "secondary_failure_probability": round(max(1.0, (100 - recovery) * 0.35), 1),
                "estimated_downtime_seconds": downtime,
                "simulation": "digital-twin heuristic",
            }
        return plans

    @staticmethod
    def _risk(plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for plan in plans:
            tool = plan["actions"][0]["tool"]
            risk = TOOL_RISK.get(tool, 100)
            plan["risk_score"] = risk
            plan["decision"] = "auto_execute" if risk <= 30 else "supervisor_review" if risk <= 60 else "human_approval" if risk <= 80 else "blocked"
            plan["utility_score"] = round(plan["expected_recovery_pct"] - risk * 0.45 - plan["estimated_downtime_seconds"] * 0.08, 2)
        plans.sort(key=lambda plan: plan["utility_score"], reverse=True)
        return plans

    def _remember(self, incident: Incident, plan: Dict[str, Any], outcome: str, duration: float) -> Dict[str, Any]:
        self.registry.require("memory", "write_memory")
        action = plan["actions"][0]["tool"]
        self.memory.remember(
            incident_id=incident.incident_id,
            root_cause=incident.root_cause or "unknown",
            pattern=incident.metadata.get("pattern", "unknown"),
            action=action,
            outcome=outcome,
            severity=incident.severity.value,
            affected_assets=incident.affected_assets,
            duration_seconds=duration,
        )
        return {"summary": f"Stored episodic memory and updated procedure success rate for {action}", "outcome": outcome}

    async def _prediction_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(8)
                created = self.traces.run("predictor", "Prediction Engine", "Scan metric trends", None, self.predictor.scan)
                for prediction in created:
                    self.audit.append("predictor", "prediction_created", resource=prediction["asset_id"], details=prediction)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.audit.append("predictor", "prediction_scan", outcome="failed", details={"error": str(exc)})

    async def wait_for_incident(self, incident_id: str, timeout: float = 15.0) -> Incident | None:
        task = self._tasks.get(incident_id)
        if task:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        return self.world.incidents.get(incident_id)

    def prevent_prediction(self, prediction_id: str) -> Incident | None:
        prediction = next(
            (item for item in self.predictor.predictions.values() if item.prediction_id == prediction_id),
            None,
        )
        if not prediction or prediction.acknowledged:
            return None
        asset = self.world.assets.get(prediction.asset_id)
        if not asset:
            return None
        incident = self.world.create_incident(
            title=f"Prevent {prediction.metric_name} threshold breach",
            description=(
                f"Trend analysis predicts {prediction.asset_id} will reach "
                f"{prediction.threshold} for {prediction.metric_name}"
            ),
            severity="medium",
            affected_assets=[prediction.asset_id],
            incident_type="predictive",
        )
        incident.metadata.update({
            "pattern": "predicted_resource_pressure",
            "target_asset": prediction.asset_id,
            "prediction_id": prediction.prediction_id,
        })
        prediction.acknowledged = True
        self.audit.append(
            "predictor", "preventive_incident_created", incident_id=incident.incident_id,
            resource=prediction.asset_id, details={"prediction_id": prediction.prediction_id},
        )
        return incident

    def status(self) -> Dict[str, Any]:
        active = sum(1 for task in self._tasks.values() if not task.done())
        return {
            "status": "operational",
            "active_pipelines": active,
            "completed_pipelines": sum(1 for task in self._tasks.values() if task.done()),
            "registry": self.registry.summary(),
            "memory": self.memory.summary(),
            "predictions_active": len(self.predictor.list()),
            "ai": self.reasoner.status,
            "gateway": {"status": "enforcing", "rate_limit_per_minute": self.gateway.rate_limit},
        }
