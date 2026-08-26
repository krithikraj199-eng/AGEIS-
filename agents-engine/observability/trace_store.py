"""
Trace Storage and Data Model for AEGIS Ω OpenTelemetry Instrumentation.
Maintains persistent span records indexed by incident_id.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SpanRecord(BaseModel):
    """
    Standard OpenTelemetry Span Record for AEGIS Ω:
    { incident_id, agent_id, timestamp, status, summary, duration_ms, attributes }
    """
    incident_id: str
    agent_id: str
    span_name: str
    status: str = "SUCCESS"  # STARTED, DETECTED, SUCCESS, FAILED, HELD
    summary: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    time_formatted: str = ""
    duration_ms: float = 0.0
    attributes: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.time_formatted:
            try:
                dt = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
                self.time_formatted = dt.strftime("%H:%M:%S")
            except Exception:
                self.time_formatted = datetime.now().strftime("%H:%M:%S")


class TraceStore:
    """
    In-memory and disk-persisted trace store for all incident execution traces.
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path("data/traces")
        self._in_memory_records: List[SpanRecord] = []
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create trace directory: {e}")

    def record_span(self, span: SpanRecord) -> None:
        """Store span record in memory and persist to disk."""
        self._in_memory_records.append(span)

        if span.incident_id:
            try:
                clean_id = span.incident_id.replace("/", "_").replace("\\", "_")
                file_path = self.storage_dir / f"{clean_id}.jsonl"
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(span.model_dump_json() + "\n")
            except Exception as e:
                logger.warning(f"Failed to persist span record: {e}")

    def get_trace(self, incident_id: str) -> List[SpanRecord]:
        """Retrieve all recorded spans for an incident in chronological order."""
        # 1. Check in-memory records matching incident_id or correlation_id
        records = [
            r for r in self._in_memory_records
            if (r.incident_id == incident_id)
            or (incident_id and r.incident_id and (incident_id in r.incident_id or r.incident_id in incident_id))
            or (r.attributes.get("correlation_id") and incident_id and (r.attributes.get("correlation_id") in incident_id or incident_id in str(r.attributes.get("correlation_id"))))
        ]

        # 2. If not found or incomplete, load from disk
        clean_id = incident_id.replace("/", "_").replace("\\", "_")
        file_path = self.storage_dir / f"{clean_id}.jsonl"
        if file_path.exists():
            disk_records: List[SpanRecord] = []
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            disk_records.append(SpanRecord.model_validate_json(line))
            except Exception as e:
                logger.warning(f"Failed reading trace file: {e}")

            # Merge records avoiding duplicates
            seen = {(r.agent_id, r.timestamp, r.status) for r in records}
            for dr in disk_records:
                key = (dr.agent_id, dr.timestamp, dr.status)
                if key not in seen:
                    records.append(dr)
                    seen.add(key)

        # Sort chronologically by timestamp
        records.sort(key=lambda r: r.timestamp)
        return records

    def get_all_incident_ids(self) -> List[str]:
        """List all incident IDs with recorded traces."""
        ids = set(r.incident_id for r in self._in_memory_records if r.incident_id)
        if self.storage_dir.exists():
            for p in self.storage_dir.glob("*.jsonl"):
                ids.add(p.stem)
        return sorted(list(ids))

    def clear(self) -> None:
        """Clear trace records (useful for testing)."""
        self._in_memory_records.clear()
        if self.storage_dir.exists():
            for p in self.storage_dir.glob("*.jsonl"):
                try:
                    p.unlink()
                except Exception:
                    pass


# Global singleton instance
trace_store = TraceStore()
