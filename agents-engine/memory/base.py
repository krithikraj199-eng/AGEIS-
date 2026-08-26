"""
Memory Models and Interfaces for AEGIS Ω.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IncidentContext(BaseModel):
    """Context state tracking an active incident lifecycle."""
    incident_id: str
    correlation_id: str
    root_asset_id: Optional[str] = None
    affected_assets: List[str] = Field(default_factory=list)
    detected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "OPEN"
    hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    remediation_plan_id: Optional[str] = None
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)


class MemoryStore:
    """In-memory state and working context store."""

    def __init__(self):
        self._incidents: Dict[str, IncidentContext] = {}

    def get_or_create_incident(self, correlation_id: str, incident_id: Optional[str] = None) -> IncidentContext:
        if correlation_id not in self._incidents:
            inc_id = incident_id or f"INC-{correlation_id[:8]}"
            self._incidents[correlation_id] = IncidentContext(
                incident_id=inc_id,
                correlation_id=correlation_id,
            )
        return self._incidents[correlation_id]

    def get_incident(self, correlation_id: str) -> Optional[IncidentContext]:
        return self._incidents.get(correlation_id)
