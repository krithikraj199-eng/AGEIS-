"""
AEGIS Ω — Chaos Engine

Provides controllable failure injection scenarios including
single-asset stress, multi-asset cascading failures, and
complex attack simulations.

This is the "Chaos Lab" — the interactive demo showpiece.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from .models import (
    Asset, AssetStatus, Event, EventType, Incident,
    IncidentStatus, IncidentType, Severity
)
from .metrics import MetricsEngine
from .events import EventEngine
from .dependencies import DependencyGraph


# ═══════════════════════════════════════════════════════════
# FAILURE SCENARIO DEFINITIONS
# ═══════════════════════════════════════════════════════════

FAILURE_SCENARIOS = {
    "database_crisis": {
        "name": "🔥 Database Connection Crisis",
        "description": "Database connection pool exhaustion causing cascading API timeouts",
        "target_asset": "DB-MAIN-01",
        "stress_chain": [
            {"asset": "DB-MAIN-01", "stress": "connection_flood", "intensity": 0.9, "delay": 0},
            {"asset": "DB-MAIN-01", "stress": "response_degradation", "intensity": 0.8, "delay": 0},
            {"asset": "DB-MAIN-01", "stress": "cpu_spike", "intensity": 0.7, "delay": 1},
            {"asset": "DB-MAIN-02", "stress": "connection_flood", "intensity": 0.6, "delay": 2},
            {"asset": "SVC-AUTH-01", "stress": "response_degradation", "intensity": 0.7, "delay": 3},
            {"asset": "SVC-CACHE-01", "stress": "error_spike", "intensity": 0.5, "delay": 3},
            {"asset": "API-STUDENT-01", "stress": "response_degradation", "intensity": 0.8, "delay": 5},
            {"asset": "API-STAFF-01", "stress": "response_degradation", "intensity": 0.7, "delay": 5},
            {"asset": "API-EXAM-01", "stress": "error_spike", "intensity": 0.6, "delay": 6},
            {"asset": "APP-PORTAL-01", "stress": "error_spike", "intensity": 0.8, "delay": 8},
            {"asset": "APP-PORTAL-02", "stress": "error_spike", "intensity": 0.7, "delay": 8},
            {"asset": "APP-ERP-01", "stress": "error_spike", "intensity": 0.9, "delay": 9},
        ],
        "severity": Severity.CRITICAL,
    },
    "memory_leak": {
        "name": "💧 Progressive Memory Leak",
        "description": "Application server memory leak causing gradual degradation",
        "target_asset": "SRV-CSE-WEB-01",
        "stress_chain": [
            {"asset": "SRV-CSE-WEB-01", "stress": "memory_leak", "intensity": 0.5, "delay": 0},
            {"asset": "SRV-CSE-WEB-01", "stress": "response_degradation", "intensity": 0.3, "delay": 3},
            {"asset": "SRV-CSE-WEB-02", "stress": "cpu_spike", "intensity": 0.4, "delay": 5},
            {"asset": "APP-LMS-01", "stress": "response_degradation", "intensity": 0.5, "delay": 7},
        ],
        "severity": Severity.HIGH,
    },
    "network_failure": {
        "name": "🌐 Network Segment Failure",
        "description": "Core switch failure isolating multiple departments",
        "target_asset": "NET-CORE-01",
        "stress_chain": [
            {"asset": "NET-CORE-01", "stress": "network_latency", "intensity": 1.0, "delay": 0},
            {"asset": "NET-DIST-CSE", "stress": "network_latency", "intensity": 0.9, "delay": 1},
            {"asset": "NET-DIST-ECE", "stress": "network_latency", "intensity": 0.9, "delay": 1},
            {"asset": "NET-DIST-ADMIN", "stress": "network_latency", "intensity": 0.8, "delay": 1},
            {"asset": "NET-WIFI-01", "stress": "network_latency", "intensity": 0.9, "delay": 2},
            {"asset": "LB-WEB-01", "stress": "error_spike", "intensity": 0.7, "delay": 3},
            {"asset": "LB-API-01", "stress": "error_spike", "intensity": 0.7, "delay": 3},
            {"asset": "SVC-CACHE-01", "stress": "error_spike", "intensity": 0.8, "delay": 4},
            {"asset": "DNS-01", "stress": "response_degradation", "intensity": 0.6, "delay": 2},
        ],
        "severity": Severity.CRITICAL,
    },
    "disk_exhaustion": {
        "name": "💾 Disk Space Exhaustion",
        "description": "Log accumulation exhausting disk on central log server",
        "target_asset": "LOG-01",
        "stress_chain": [
            {"asset": "LOG-01", "stress": "disk_exhaustion", "intensity": 0.9, "delay": 0},
            {"asset": "SAN-02", "stress": "disk_exhaustion", "intensity": 0.6, "delay": 3},
            {"asset": "DB-ANALYTICS-01", "stress": "disk_exhaustion", "intensity": 0.5, "delay": 5},
            {"asset": "BACKUP-01", "stress": "error_spike", "intensity": 0.7, "delay": 7},
        ],
        "severity": Severity.HIGH,
    },
    "service_crash": {
        "name": "⚡ Authentication Service Crash",
        "description": "Auth service failure locking out all users",
        "target_asset": "SVC-AUTH-01",
        "stress_chain": [
            {"asset": "SVC-AUTH-01", "stress": "cpu_spike", "intensity": 1.0, "delay": 0},
            {"asset": "SVC-AUTH-01", "stress": "error_spike", "intensity": 1.0, "delay": 0},
            {"asset": "SVC-AUTH-02", "stress": "connection_flood", "intensity": 0.8, "delay": 2},
            {"asset": "APP-PORTAL-01", "stress": "error_spike", "intensity": 0.9, "delay": 3},
            {"asset": "APP-PORTAL-02", "stress": "error_spike", "intensity": 0.9, "delay": 3},
            {"asset": "APP-EXAM-01", "stress": "error_spike", "intensity": 0.9, "delay": 4},
            {"asset": "APP-FINANCE-01", "stress": "error_spike", "intensity": 0.8, "delay": 4},
            {"asset": "APP-LMS-01", "stress": "error_spike", "intensity": 0.8, "delay": 5},
            {"asset": "APP-ERP-01", "stress": "error_spike", "intensity": 0.9, "delay": 5},
            {"asset": "APP-HR-01", "stress": "error_spike", "intensity": 0.7, "delay": 6},
        ],
        "severity": Severity.CRITICAL,
    },
    "security_attack": {
        "name": "🛡️ Credential Stuffing Attack",
        "description": "Automated credential attacks with suspicious login patterns",
        "target_asset": "SVC-AUTH-01",
        "stress_chain": [
            {"asset": "SVC-AUTH-01", "stress": "connection_flood", "intensity": 0.7, "delay": 0},
            {"asset": "SVC-AUTH-01", "stress": "cpu_spike", "intensity": 0.5, "delay": 1},
            {"asset": "LDAP-01", "stress": "connection_flood", "intensity": 0.6, "delay": 2},
            {"asset": "FW-MAIN-01", "stress": "cpu_spike", "intensity": 0.4, "delay": 3},
        ],
        "severity": Severity.HIGH,
        "is_security": True,
    },
    "deployment_regression": {
        "name": "🚀 Bad Deployment Rollout",
        "description": "Failed deployment causing application errors",
        "target_asset": "APP-PORTAL-01",
        "stress_chain": [
            {"asset": "APP-PORTAL-01", "stress": "error_spike", "intensity": 0.8, "delay": 0},
            {"asset": "APP-PORTAL-01", "stress": "response_degradation", "intensity": 0.7, "delay": 1},
            {"asset": "APP-PORTAL-01", "stress": "cpu_spike", "intensity": 0.5, "delay": 2},
            {"asset": "API-STUDENT-01", "stress": "error_spike", "intensity": 0.4, "delay": 4},
        ],
        "severity": Severity.HIGH,
    },
    "cpu_storm": {
        "name": "🔥 Compute Storm",
        "description": "Runaway process consuming CPU across compute nodes",
        "target_asset": "SRV-CSE-GPU-01",
        "stress_chain": [
            {"asset": "SRV-CSE-GPU-01", "stress": "cpu_spike", "intensity": 1.0, "delay": 0},
            {"asset": "SRV-CSE-WEB-01", "stress": "cpu_spike", "intensity": 0.7, "delay": 2},
            {"asset": "SRV-CSE-WEB-02", "stress": "cpu_spike", "intensity": 0.6, "delay": 3},
            {"asset": "SRV-CSE-DEV-01", "stress": "cpu_spike", "intensity": 0.5, "delay": 4},
            {"asset": "NET-DIST-CSE", "stress": "network_latency", "intensity": 0.4, "delay": 5},
        ],
        "severity": Severity.HIGH,
    },
    "queue_overflow": {
        "name": "📬 Message Queue Overflow",
        "description": "Message queue backing up causing notification and processing delays",
        "target_asset": "SVC-QUEUE-01",
        "stress_chain": [
            {"asset": "SVC-QUEUE-01", "stress": "queue_backup", "intensity": 0.9, "delay": 0},
            {"asset": "SVC-QUEUE-01", "stress": "memory_leak", "intensity": 0.5, "delay": 2},
            {"asset": "API-NOTIFICATION-01", "stress": "response_degradation", "intensity": 0.7, "delay": 3},
            {"asset": "SVC-REPORT-01", "stress": "error_spike", "intensity": 0.6, "delay": 5},
        ],
        "severity": Severity.MEDIUM,
    },
    "cascading_total": {
        "name": "💥 Total Cascading Failure",
        "description": "Storage failure cascading through entire infrastructure",
        "target_asset": "SAN-01",
        "stress_chain": [
            {"asset": "SAN-01", "stress": "disk_exhaustion", "intensity": 1.0, "delay": 0},
            {"asset": "SAN-01", "stress": "throughput_drop", "intensity": 0.9, "delay": 0},
            {"asset": "DB-MAIN-01", "stress": "response_degradation", "intensity": 0.9, "delay": 2},
            {"asset": "DB-MAIN-01", "stress": "error_spike", "intensity": 0.7, "delay": 3},
            {"asset": "DB-MAIN-02", "stress": "response_degradation", "intensity": 0.8, "delay": 3},
            {"asset": "DB-STUDENT-01", "stress": "error_spike", "intensity": 0.8, "delay": 4},
            {"asset": "DB-EXAM-01", "stress": "error_spike", "intensity": 0.7, "delay": 4},
            {"asset": "SVC-AUTH-01", "stress": "error_spike", "intensity": 0.8, "delay": 5},
            {"asset": "SVC-CACHE-01", "stress": "error_spike", "intensity": 0.6, "delay": 5},
            {"asset": "SVC-FILE-01", "stress": "error_spike", "intensity": 0.9, "delay": 3},
            {"asset": "API-STUDENT-01", "stress": "error_spike", "intensity": 0.9, "delay": 7},
            {"asset": "API-EXAM-01", "stress": "error_spike", "intensity": 0.8, "delay": 7},
            {"asset": "API-FINANCE-01", "stress": "error_spike", "intensity": 0.8, "delay": 7},
            {"asset": "APP-PORTAL-01", "stress": "error_spike", "intensity": 1.0, "delay": 9},
            {"asset": "APP-ERP-01", "stress": "error_spike", "intensity": 1.0, "delay": 9},
            {"asset": "APP-EXAM-01", "stress": "error_spike", "intensity": 0.9, "delay": 10},
            {"asset": "APP-FINANCE-01", "stress": "error_spike", "intensity": 0.9, "delay": 10},
        ],
        "severity": Severity.CRITICAL,
    },
}


class ChaosEngine:
    """
    Manages failure injection, cascading propagation,
    and recovery for the digital institution.
    """

    def __init__(self, metrics_engine: MetricsEngine,
                 event_engine: EventEngine,
                 dep_graph: DependencyGraph,
                 assets: Dict[str, Asset]):
        self.metrics = metrics_engine
        self.events = event_engine
        self.dep_graph = dep_graph
        self.assets = assets

        # Active failures tracking
        self.active_failures: Dict[str, Dict[str, Any]] = {}
        self.failure_history: List[Dict[str, Any]] = []
        self.incident_callback: Optional[Callable] = None

    def set_incident_callback(self, cb: Callable):
        """Register a callback for when an incident should be created."""
        self.incident_callback = cb

    # ──────────────────────────────────────────────────────
    # INJECT FAILURE
    # ──────────────────────────────────────────────────────

    def inject_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """
        Inject a predefined failure scenario.
        Returns the details of the injected failure.
        """
        scenario = FAILURE_SCENARIOS.get(scenario_id)
        if not scenario:
            return None

        failure_id = f"FAIL-{uuid.uuid4().hex[:8].upper()}"
        correlation_id = self.events.new_correlation_id()
        affected_assets: Set[str] = set()

        # Apply stress chain
        applied: List[Dict[str, Any]] = []
        for step in scenario["stress_chain"]:
            asset_id = step["asset"]
            if asset_id not in self.assets:
                continue

            asset = self.assets[asset_id]
            self.metrics.apply_stress(asset, step["stress"], step["intensity"])
            affected_assets.add(asset_id)

            # Generate event
            event = self.events.create_event(
                asset_id=asset_id,
                event_type=self._stress_to_event_type(step["stress"]),
                severity=scenario["severity"],
                message=f"[CHAOS] {scenario['name']}: {step['stress']} on {asset.name}",
                correlation_id=correlation_id,
                metadata={
                    "chaos_scenario": scenario_id,
                    "failure_id": failure_id,
                    "stress_type": step["stress"],
                    "intensity": step["intensity"],
                }
            )
            applied.append({
                "asset_id": asset_id,
                "asset_name": asset.name,
                "stress": step["stress"],
                "intensity": step["intensity"],
            })

        # Calculate blast radius from dependency graph
        blast = self.dep_graph.get_blast_radius(scenario["target_asset"])

        failure_record = {
            "failure_id": failure_id,
            "scenario_id": scenario_id,
            "scenario_name": scenario["name"],
            "description": scenario["description"],
            "severity": scenario["severity"].value,
            "target_asset": scenario["target_asset"],
            "correlation_id": correlation_id,
            "affected_assets": list(affected_assets),
            "applied_stress": applied,
            "blast_radius": blast["total_affected"],
            "is_security": scenario.get("is_security", False),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }

        self.active_failures[failure_id] = failure_record
        self.failure_history.append(failure_record)

        # Create incident via callback
        if self.incident_callback:
            self.incident_callback(failure_record)

        return failure_record

    # ──────────────────────────────────────────────────────
    # INJECT CUSTOM SINGLE-ASSET STRESS
    # ──────────────────────────────────────────────────────

    def inject_stress(self, asset_id: str, stress_type: str,
                      intensity: float = 0.7) -> Optional[Dict[str, Any]]:
        """Inject stress on a single asset."""
        if asset_id not in self.assets:
            return None

        asset = self.assets[asset_id]
        self.metrics.apply_stress(asset, stress_type, intensity)

        failure_id = f"FAIL-{uuid.uuid4().hex[:8].upper()}"
        correlation_id = self.events.new_correlation_id()

        self.events.create_event(
            asset_id=asset_id,
            event_type=self._stress_to_event_type(stress_type),
            severity=Severity.HIGH,
            message=f"[CHAOS] {stress_type} injected on {asset.name}",
            correlation_id=correlation_id,
            metadata={"stress_type": stress_type, "intensity": intensity},
        )

        record = {
            "failure_id": failure_id,
            "scenario_id": "custom",
            "target_asset": asset_id,
            "stress_type": stress_type,
            "intensity": intensity,
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }
        self.active_failures[failure_id] = record
        return record

    # ──────────────────────────────────────────────────────
    # RECOVER
    # ──────────────────────────────────────────────────────

    def recover_failure(self, failure_id: str,
                        recovery_pct: float = 0.8) -> bool:
        """Recover from an injected failure."""
        failure = self.active_failures.get(failure_id)
        if not failure or not failure.get("active"):
            return False

        scenario_id = failure.get("scenario_id")
        if scenario_id and scenario_id in FAILURE_SCENARIOS:
            scenario = FAILURE_SCENARIOS[scenario_id]
            for step in scenario["stress_chain"]:
                asset_id = step["asset"]
                if asset_id in self.assets:
                    self.metrics.relieve_stress(
                        self.assets[asset_id],
                        step["stress"],
                        recovery_pct
                    )
        elif failure.get("target_asset"):
            asset_id = failure["target_asset"]
            if asset_id in self.assets:
                stress = failure.get("stress_type", "cpu_spike")
                self.metrics.relieve_stress(
                    self.assets[asset_id], stress, recovery_pct
                )

        failure["active"] = False
        return True

    def recover_all(self, recovery_pct: float = 0.8):
        """Recover from all active failures."""
        for fid in list(self.active_failures.keys()):
            self.recover_failure(fid, recovery_pct)

    # ──────────────────────────────────────────────────────
    # QUERIES
    # ──────────────────────────────────────────────────────

    def get_active_failures(self) -> List[Dict[str, Any]]:
        return [f for f in self.active_failures.values() if f.get("active")]

    def get_failure_history(self, last_n: int = 50) -> List[Dict[str, Any]]:
        return self.failure_history[-last_n:]

    def get_available_scenarios(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": sid,
                "name": s["name"],
                "description": s["description"],
                "target": s["target_asset"],
                "severity": s["severity"].value,
                "affected_count": len(s["stress_chain"]),
            }
            for sid, s in FAILURE_SCENARIOS.items()
        ]

    # ──────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _stress_to_event_type(stress: str) -> EventType:
        mapping = {
            "cpu_spike": EventType.CPU_CRITICAL,
            "memory_leak": EventType.MEMORY_CRITICAL,
            "disk_exhaustion": EventType.DISK_FULL,
            "network_latency": EventType.NETWORK_FAILURE,
            "connection_flood": EventType.DATABASE_OVERLOAD,
            "error_spike": EventType.APPLICATION_ERROR,
            "response_degradation": EventType.DATABASE_TIMEOUT,
            "queue_backup": EventType.SERVICE_DEGRADED,
            "throughput_drop": EventType.SERVICE_DEGRADED,
        }
        return mapping.get(stress, EventType.APPLICATION_ERROR)
