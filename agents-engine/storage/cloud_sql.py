"""
Cloud SQL PostgreSQL Storage Adapter for AEGIS Ω Intelligence Engine.
Stores persistent relational records for:
- Incidents
- Remediation Plans
- Audit Records
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from runtime.config import get_settings

logger = logging.getLogger(__name__)


class IncidentDBRecord(BaseModel):
    """Schema for incident row in Cloud SQL."""
    incident_id: str
    correlation_id: str
    asset_id: str
    event_type: str = "SYSTEM_ANOMALY"
    severity: str = "HIGH"
    status: str = "DETECTED"
    root_cause: Optional[str] = None
    blast_radius: Optional[float] = None
    detected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class PlanDBRecord(BaseModel):
    """Schema for remediation plan row in Cloud SQL."""
    plan_id: str
    incident_id: str
    correlation_id: str
    strategy: str
    risk_estimate: str
    risk_score: int = 50
    rollback_method: str
    actions_json: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditDBRecord(BaseModel):
    """Schema for execution audit row in Cloud SQL."""
    audit_id: str
    timestamp: str
    plan_id: str
    tool_name: str
    params_json: Dict[str, Any] = Field(default_factory=dict)
    actor: str = "ExecutorAgent"
    risk_score: int = 0
    status: str = "SUCCESS"
    result_json: Dict[str, Any] = Field(default_factory=dict)


class CloudSQLStorage:
    """
    Cloud SQL PostgreSQL client adapter.
    Operates in live PostgreSQL mode when configured, or transparent in-memory mode in local testing.
    """

    def __init__(self, enable_cloud_sql: Optional[bool] = None):
        settings = get_settings()
        self.enable_cloud_sql = (
            enable_cloud_sql if enable_cloud_sql is not None else settings.enable_cloud_sql
        )
        self.connection_name = settings.cloud_sql_connection_name
        self.database = settings.cloud_sql_database
        self.user = settings.cloud_sql_user
        self.password = settings.cloud_sql_password.get_secret_value() if settings.cloud_sql_password else None
        self.host = settings.cloud_sql_host
        self.port = settings.cloud_sql_port

        # Local in-memory storage fallback
        self._incidents: Dict[str, IncidentDBRecord] = {}
        self._plans: Dict[str, PlanDBRecord] = {}
        self._audit_records: List[AuditDBRecord] = []
        self._pool = None

    async def initialize(self) -> None:
        """Initialize database tables and connection pool if enabled."""
        if self.enable_cloud_sql and self.password:
            try:
                import asyncpg
                self._pool = await asyncpg.create_pool(
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    host=self.host,
                    port=self.port,
                    min_size=1,
                    max_size=10,
                )
                await self._create_tables_if_not_exist()
                logger.info("Connected to Cloud SQL PostgreSQL database.")
            except Exception as e:
                logger.warning(
                    f"Could not connect to Cloud SQL ({e}). Operating in resilient fallback mode."
                )
                self._pool = None

    async def _create_tables_if_not_exist(self) -> None:
        """Create PostgreSQL tables."""
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id VARCHAR(128) PRIMARY KEY,
                    correlation_id VARCHAR(128) NOT NULL,
                    asset_id VARCHAR(128) NOT NULL,
                    event_type VARCHAR(64) NOT NULL,
                    severity VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    root_cause TEXT,
                    blast_radius FLOAT,
                    detected_at TIMESTAMPTZ NOT NULL,
                    resolved_at TIMESTAMPTZ,
                    metadata_json JSONB
                );
                CREATE TABLE IF NOT EXISTS remediation_plans (
                    plan_id VARCHAR(128) PRIMARY KEY,
                    incident_id VARCHAR(128) REFERENCES incidents(incident_id),
                    correlation_id VARCHAR(128) NOT NULL,
                    strategy VARCHAR(64) NOT NULL,
                    risk_estimate VARCHAR(32) NOT NULL,
                    risk_score INTEGER NOT NULL,
                    rollback_method TEXT NOT NULL,
                    actions_json JSONB,
                    created_at TIMESTAMPTZ NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_records (
                    audit_id VARCHAR(128) PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    plan_id VARCHAR(128),
                    tool_name VARCHAR(64) NOT NULL,
                    params_json JSONB,
                    actor VARCHAR(64) NOT NULL,
                    risk_score INTEGER,
                    status VARCHAR(32) NOT NULL,
                    result_json JSONB
                );
            """)

    async def save_incident(self, incident: Dict[str, Any]) -> str:
        """Insert or update an incident record."""
        rec = IncidentDBRecord(
            incident_id=incident["incident_id"],
            correlation_id=incident.get("correlation_id", ""),
            asset_id=incident.get("asset_id", "UNKNOWN"),
            event_type=str(incident.get("event_type", "SYSTEM_ANOMALY")),
            severity=str(incident.get("severity", "HIGH")),
            status=incident.get("status", "DETECTED"),
            root_cause=incident.get("root_cause"),
            blast_radius=incident.get("blast_radius"),
            detected_at=incident.get("detected_at", datetime.now(timezone.utc).isoformat()),
            resolved_at=incident.get("resolved_at"),
            metadata_json=incident.get("metadata", {}),
        )
        self._incidents[rec.incident_id] = rec

        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO incidents (incident_id, correlation_id, asset_id, event_type, severity, status, root_cause, blast_radius, detected_at, resolved_at, metadata_json)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (incident_id) DO UPDATE SET
                            status = EXCLUDED.status,
                            root_cause = EXCLUDED.root_cause,
                            resolved_at = EXCLUDED.resolved_at,
                            metadata_json = EXCLUDED.metadata_json;
                    """, rec.incident_id, rec.correlation_id, rec.asset_id, rec.event_type, rec.severity, rec.status, rec.root_cause, rec.blast_radius, rec.detected_at, rec.resolved_at, json.dumps(rec.metadata_json))
            except Exception as e:
                logger.error(f"Cloud SQL error saving incident: {e}")

        return rec.incident_id

    async def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an incident by ID."""
        if incident_id in self._incidents:
            return self._incidents[incident_id].model_dump()
        return None

    async def save_plan(self, plan: Dict[str, Any]) -> str:
        """Insert a remediation plan record."""
        rec = PlanDBRecord(
            plan_id=plan["plan_id"],
            incident_id=plan.get("incident_id", ""),
            correlation_id=plan.get("correlation_id", ""),
            strategy=plan.get("strategy", "restart"),
            risk_estimate=plan.get("risk_estimate", "LOW"),
            risk_score=int(plan.get("risk_score", 50)),
            rollback_method=plan.get("rollback_method", ""),
            actions_json=plan.get("actions", []),
        )
        self._plans[rec.plan_id] = rec
        return rec.plan_id

    async def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a remediation plan by ID."""
        if plan_id in self._plans:
            return self._plans[plan_id].model_dump()
        return None

    async def save_audit_record(self, audit: Dict[str, Any]) -> str:
        """Record an execution audit entry."""
        audit_id = audit.get("audit_id", f"AUD-{len(self._audit_records)+1:04d}")
        rec = AuditDBRecord(
            audit_id=audit_id,
            timestamp=audit.get("timestamp", datetime.now(timezone.utc).isoformat()),
            plan_id=audit.get("plan_id", ""),
            tool_name=audit.get("tool_name", ""),
            params_json=audit.get("params", {}),
            actor=audit.get("actor", "ExecutorAgent"),
            risk_score=int(audit.get("risk_score", 0)),
            status=audit.get("status", "SUCCESS"),
            result_json=audit.get("result", {}),
        )
        self._audit_records.append(rec)
        return audit_id

    async def list_audit_records(self) -> List[Dict[str, Any]]:
        """Retrieve all recorded audit entries."""
        return [r.model_dump() for r in self._audit_records]

    def clear(self) -> None:
        """Clear local storage cache."""
        self._incidents.clear()
        self._plans.clear()
        self._audit_records.clear()


# Global singleton instance
_global_cloud_sql: Optional[CloudSQLStorage] = None


def get_cloud_sql_storage() -> CloudSQLStorage:
    """Retrieve or initialize the global CloudSQLStorage singleton."""
    global _global_cloud_sql
    if _global_cloud_sql is None:
        _global_cloud_sql = CloudSQLStorage()
    return _global_cloud_sql
