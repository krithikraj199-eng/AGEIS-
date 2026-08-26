"""
Episodic Memory for AEGIS Ω Memory Bank.
Stores immutable records of completed and mitigated incidents:
{ incident, root cause, plan, outcome, timestamps, blast radius }
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .storage import EpisodicStoreProtocol, InMemoryStorageBackend

logger = logging.getLogger(__name__)


class EpisodeRecord(BaseModel):
    """
    Required schema for episodic incident record:
    { incident, root cause, plan, outcome, timestamps, blast radius }
    """
    incident_id: str
    correlation_id: str
    root_cause: str
    plan: Dict[str, Any] = Field(default_factory=dict)
    outcome: str = "SUCCESS"  # SUCCESS, FAILED, ESCALATED
    timestamps: Dict[str, str] = Field(default_factory=dict)
    blast_radius: Dict[str, Any] = Field(default_factory=dict)
    incident_signature: str = "GENERIC_ANOMALY"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EpisodicMemory:
    """
    Episodic Memory engine for recording and retrieving historical incidents.
    """

    def __init__(self, store: Optional[EpisodicStoreProtocol] = None):
        self.store = store or InMemoryStorageBackend()

    def record_episode(
        self,
        incident_id: str,
        correlation_id: str,
        root_cause: str,
        plan: Dict[str, Any],
        outcome: str = "SUCCESS",
        timestamps: Optional[Dict[str, str]] = None,
        blast_radius: Optional[Dict[str, Any]] = None,
        incident_signature: Optional[str] = None,
    ) -> EpisodeRecord:
        """Store an episodic incident record after mitigation."""
        sig = incident_signature or f"{root_cause[:30].strip().replace(' ', '_').upper()}"
        ts_dict = timestamps or {"resolved_at": datetime.now(timezone.utc).isoformat()}
        br_dict = blast_radius or {}

        record = EpisodeRecord(
            incident_id=incident_id,
            correlation_id=correlation_id,
            root_cause=root_cause,
            plan=dict(plan),
            outcome=outcome,
            timestamps=ts_dict,
            blast_radius=br_dict,
            incident_signature=sig,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self.store.save_episode(record.model_dump())
        logger.info(f"Episodic memory stored for incident '{incident_id}' (Outcome: {outcome}).")
        return record

    def get_episode(self, incident_id: str) -> Optional[EpisodeRecord]:
        """Retrieve a specific incident episode by ID."""
        raw = self.store.get_episode(incident_id)
        if raw:
            return EpisodeRecord.model_validate(raw)
        return None

    def search_episodes(
        self,
        query: str = "",
        signature: Optional[str] = None,
        limit: int = 10,
    ) -> List[EpisodeRecord]:
        """Search historical episodes by text query or signature."""
        raw_list = self.store.query_episodes(query=query, signature=signature, limit=limit)
        return [EpisodeRecord.model_validate(r) for r in raw_list]

    def list_episodes(self) -> List[EpisodeRecord]:
        """List all episodic incident records."""
        raw_list = self.store.list_all_episodes()
        return [EpisodeRecord.model_validate(r) for r in raw_list]

    def clear(self) -> None:
        """Clear all episodic records."""
        if hasattr(self.store, "clear"):
            self.store.clear()
