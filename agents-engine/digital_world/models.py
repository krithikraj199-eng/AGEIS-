"""
Digital World Schema Models for AEGIS Ω Integration.
Defines data structures for Events, Metrics, Topology, History, and Actions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class DigitalWorldEventType(str, Enum):
    """Supported event types in the Digital World telemetry stream."""
    CPU_NORMAL = "CPU_NORMAL"
    MEMORY_WARNING = "MEMORY_WARNING"
    DISK_FULL = "DISK_FULL"
    NETWORK_LATENCY = "NETWORK_LATENCY"
    DATABASE_TIMEOUT = "DATABASE_TIMEOUT"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    SERVICE_CRASH = "SERVICE_CRASH"
    DEPLOYMENT_CHANGE = "DEPLOYMENT_CHANGE"
    SECURITY_ALERT = "SECURITY_ALERT"
    SYSTEM_ANOMALY = "SYSTEM_ANOMALY"


class DigitalWorldSeverity(str, Enum):
    """Event severity levels."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DigitalWorldEvent(BaseModel):
    """
    Standard event schema matching Member 1's Event stream interface:
    {
        timestamp,
        asset_id,
        event_type,
        severity,
        metrics,
        source,
        correlation_id
    }
    """
    timestamp: str = Field(
        description="ISO 8601 UTC timestamp of the event",
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    asset_id: str = Field(
        description="Unique identifier of the target infrastructure asset or service",
    )
    event_type: str = Field(
        description="Classified system event type name",
    )
    severity: str = Field(
        description="Severity classification: INFO, LOW, MEDIUM, HIGH, CRITICAL",
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value metrics snapshot associated with the event",
    )
    source: str = Field(
        default="digital_world_engine",
        description="Originating subsystem, sensor, or telemetry collector",
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID linking related events across failure cascades",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to standard dictionary."""
        return self.model_dump()


class MetricReading(BaseModel):
    """Point-in-time metric reading."""
    asset_id: str
    metric: str
    value: float
    unit: str = "raw"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class HistoricalIncidentRecord(BaseModel):
    """Record of a resolved infrastructure incident in historical store."""
    incident_id: str
    timestamp: str
    signature: str = Field(
        description="Incident signature in format <ASSET_ID>:<EVENT_TYPE>",
    )
    affected_asset: str
    root_cause: str
    resolution: str
    symptoms: List[str] = Field(default_factory=list)
    key_metrics: Dict[str, Any] = Field(default_factory=dict)


class ActionResult(BaseModel):
    """Result of an action executed on the Digital World environment."""
    action: str
    asset_id: str
    status: str = "SUCCESS"
    message: str
    execution_time_ms: float = 10.0
    details: Dict[str, Any] = Field(default_factory=dict)
