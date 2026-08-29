"""
AEGIS Ω — Data Models for the Digital World

Every object in the simulation is a Pydantic model with full
type safety.  These models are used by the event engine, the
metrics engine, the dependency graph, and all agents.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════
# ENUMERATIONS
# ═══════════════════════════════════════════════════════════

class AssetType(str, Enum):
    WORKSTATION = "workstation"
    SERVER = "server"
    DATABASE = "database"
    APPLICATION = "application"
    NETWORK_NODE = "network_node"
    SERVICE = "service"
    STORAGE = "storage"
    FIREWALL = "firewall"
    LOAD_BALANCER = "load_balancer"


class AssetStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class Department(str, Enum):
    COMPUTER_SCIENCE = "Computer Science"
    ELECTRONICS = "Electronics"
    MECHANICAL = "Mechanical"
    CIVIL = "Civil"
    ADMINISTRATION = "Administration"
    LIBRARY = "Library"
    INFRASTRUCTURE = "Infrastructure"
    SECURITY = "Security"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(str, Enum):
    CPU_NORMAL = "CPU_NORMAL"
    CPU_WARNING = "CPU_WARNING"
    CPU_CRITICAL = "CPU_CRITICAL"
    MEMORY_NORMAL = "MEMORY_NORMAL"
    MEMORY_WARNING = "MEMORY_WARNING"
    MEMORY_CRITICAL = "MEMORY_CRITICAL"
    DISK_NORMAL = "DISK_NORMAL"
    DISK_WARNING = "DISK_WARNING"
    DISK_FULL = "DISK_FULL"
    NETWORK_NORMAL = "NETWORK_NORMAL"
    NETWORK_LATENCY = "NETWORK_LATENCY"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    APPLICATION_HEALTHY = "APPLICATION_HEALTHY"
    APPLICATION_ERROR = "APPLICATION_ERROR"
    APPLICATION_CRASH = "APPLICATION_CRASH"
    DATABASE_NORMAL = "DATABASE_NORMAL"
    DATABASE_TIMEOUT = "DATABASE_TIMEOUT"
    DATABASE_OVERLOAD = "DATABASE_OVERLOAD"
    SERVICE_HEALTHY = "SERVICE_HEALTHY"
    SERVICE_DEGRADED = "SERVICE_DEGRADED"
    SERVICE_CRASH = "SERVICE_CRASH"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    DEPLOYMENT_CHANGE = "DEPLOYMENT_CHANGE"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    SECURITY_ALERT = "SECURITY_ALERT"
    BACKUP_SUCCESS = "BACKUP_SUCCESS"
    BACKUP_FAILURE = "BACKUP_FAILURE"


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    EVIDENCE_COLLECTED = "evidence_collected"
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    FAILED = "failed"
    ROLLBACK = "rollback"
    ESCALATED = "escalated"


class IncidentType(str, Enum):
    REACTIVE = "reactive"
    PREDICTIVE = "predictive"


class SecurityClassification(str, Enum):
    OPERATIONAL_FAILURE = "operational_failure"
    CONFIGURATION_ERROR = "configuration_error"
    HUMAN_ERROR = "human_error"
    SECURITY_EVENT = "security_event"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    RESTART_SERVICE = "restart_service"
    SCALE_SERVICE = "scale_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    CLEAR_CACHE = "clear_cache"
    QUARANTINE_ASSET = "quarantine_asset"
    RESTORE_CONFIGURATION = "restore_configuration"
    INCREASE_RESOURCES = "increase_resources"
    ISOLATE_NETWORK = "isolate_network"
    FAILOVER = "failover"
    BLOCK_IP = "block_ip"


class PlanStatus(str, Enum):
    PROPOSED = "proposed"
    SELECTED = "selected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# ═══════════════════════════════════════════════════════════
# CORE MODELS
# ═══════════════════════════════════════════════════════════

class AssetMetrics(BaseModel):
    """Real-time metrics for an asset."""
    cpu_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    disk_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    network_latency_ms: float = Field(default=0.0, ge=0.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    request_rate: float = Field(default=0.0, ge=0.0)
    connection_count: int = Field(default=0, ge=0)
    uptime_seconds: int = Field(default=0, ge=0)
    response_time_ms: float = Field(default=0.0, ge=0.0)
    throughput: float = Field(default=0.0, ge=0.0)
    queue_depth: int = Field(default=0, ge=0)


class Asset(BaseModel):
    """A virtual asset in the Digital Institution."""
    asset_id: str = Field(default_factory=lambda: f"ASSET-{uuid.uuid4().hex[:8].upper()}")
    name: str
    asset_type: AssetType
    department: Department
    status: AssetStatus = AssetStatus.HEALTHY
    criticality: int = Field(default=5, ge=1, le=10)  # 1=low, 10=critical
    metrics: AssetMetrics = Field(default_factory=AssetMetrics)
    dependencies: List[str] = Field(default_factory=list)  # asset_ids this depends on
    dependents: List[str] = Field(default_factory=list)    # asset_ids that depend on this
    tags: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
    last_deployment: Optional[datetime] = None
    last_config_change: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Event(BaseModel):
    """An event generated by the Digital World."""
    event_id: str = Field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:8].upper()}")
    timestamp: datetime = Field(default_factory=utc_now)
    asset_id: str
    event_type: EventType
    severity: Severity
    message: str
    metrics_snapshot: Optional[AssetMetrics] = None
    source: str = "digital_world"
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Incident(BaseModel):
    """A detected incident requiring investigation."""
    incident_id: str = Field(default_factory=lambda: f"INC-{uuid.uuid4().hex[:12].upper()}")
    title: str
    description: str
    incident_type: IncidentType = IncidentType.REACTIVE
    status: IncidentStatus = IncidentStatus.DETECTED
    severity: Severity = Severity.MEDIUM
    security_classification: Optional[SecurityClassification] = None
    affected_assets: List[str] = Field(default_factory=list)
    root_cause: Optional[str] = None
    root_cause_confidence: float = 0.0
    triggering_events: List[str] = Field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    blast_radius: int = 0
    plans: List[Dict[str, Any]] = Field(default_factory=list)
    selected_plan: Optional[str] = None
    actions_taken: List[Dict[str, Any]] = Field(default_factory=list)
    verification_result: Optional[Dict[str, Any]] = None
    resolution_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RemediationPlan(BaseModel):
    """A proposed plan to fix an incident."""
    plan_id: str = Field(default_factory=lambda: f"PLAN-{uuid.uuid4().hex[:8].upper()}")
    incident_id: str
    name: str
    description: str
    actions: List[Dict[str, Any]]
    expected_result: str
    estimated_recovery_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    estimated_downtime_seconds: float = 0.0
    blast_radius: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    rollback_method: str = ""
    status: PlanStatus = PlanStatus.PROPOSED
    counterfactual_analysis: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=utc_now)


class AgentTrace(BaseModel):
    """A trace entry for agent observability."""
    trace_id: str = Field(default_factory=lambda: f"TRC-{uuid.uuid4().hex[:8].upper()}")
    incident_id: Optional[str] = None
    agent_id: str
    agent_name: str
    action: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0
    status: str = "success"
    timestamp: datetime = Field(default_factory=utc_now)
    parent_trace_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════
# MEMORY MODELS
# ═══════════════════════════════════════════════════════════

class EpisodicMemory(BaseModel):
    """What happened — a past incident record."""
    memory_id: str = Field(default_factory=lambda: f"MEM-E-{uuid.uuid4().hex[:8].upper()}")
    incident_id: str
    root_cause: str
    action_taken: str
    outcome: str  # success / failure
    severity: Severity
    affected_assets: List[str]
    duration_seconds: float
    timestamp: datetime = Field(default_factory=utc_now)
    similarity_embedding: Optional[List[float]] = None


class SemanticMemory(BaseModel):
    """What the institution knows — reusable knowledge."""
    memory_id: str = Field(default_factory=lambda: f"MEM-S-{uuid.uuid4().hex[:8].upper()}")
    knowledge: str
    category: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_incidents: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProceduralMemory(BaseModel):
    """What works — successful strategies."""
    memory_id: str = Field(default_factory=lambda: f"MEM-P-{uuid.uuid4().hex[:8].upper()}")
    failure_pattern: str
    recommended_action: str
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    total_uses: int = 0
    successful_uses: int = 0
    avg_recovery_time_seconds: float = 0.0
    source_incidents: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


# ═══════════════════════════════════════════════════════════
# GOVERNANCE MODELS
# ═══════════════════════════════════════════════════════════

class AgentRegistryEntry(BaseModel):
    """Registered agent in the system."""
    agent_id: str
    name: str
    version: str = "1.0.0"
    status: str = "active"
    capabilities: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    health: str = "healthy"
    last_heartbeat: Optional[datetime] = None
    owner: str = "system"
    created_at: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════
# PREDICTION MODELS
# ═══════════════════════════════════════════════════════════

class Prediction(BaseModel):
    """A predicted future failure."""
    prediction_id: str = Field(default_factory=lambda: f"PRED-{uuid.uuid4().hex[:8].upper()}")
    asset_id: str
    metric_name: str
    current_value: float
    predicted_value: float
    threshold: float
    time_to_threshold_hours: float
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    trend_data: List[float] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    acknowledged: bool = False


# ═══════════════════════════════════════════════════════════
# WORLD STATE
# ═══════════════════════════════════════════════════════════

class WorldState(BaseModel):
    """Snapshot of the entire digital world at a point in time."""
    timestamp: datetime = Field(default_factory=utc_now)
    total_assets: int = 0
    healthy_assets: int = 0
    degraded_assets: int = 0
    critical_assets: int = 0
    offline_assets: int = 0
    active_incidents: int = 0
    resolved_incidents_today: int = 0
    total_events_today: int = 0
    overall_health_pct: float = 100.0
    agent_count: int = 0
    predictions_active: int = 0
