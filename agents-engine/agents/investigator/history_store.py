"""
In-Memory Historical Incident Store for AEGIS Ω Investigator Agent.
Provides historical incident retrieval and similarity search until Member 1 real history APIs exist.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HistoricalIncident(BaseModel):
    """Record of a previously resolved infrastructure incident."""
    incident_id: str
    timestamp: str
    affected_asset: str
    root_cause: str
    resolution: str
    symptoms: List[str] = Field(default_factory=list)
    key_metrics: Dict[str, Any] = Field(default_factory=dict)


class HistoricalIncidentStore:
    """
    In-memory incident repository pre-seeded with known failure archetypes.
    """

    def __init__(self):
        self._incidents: List[HistoricalIncident] = []
        self._seed_default_history()

    def _seed_default_history(self) -> None:
        """Seed realistic historical incident records."""
        self._incidents.extend([
            HistoricalIncident(
                incident_id="HIST-INC-2026-001",
                timestamp="2026-07-10T08:15:00Z",
                affected_asset="DATABASE-01",
                root_cause="Postgres connection pool exhaustion caused by unindexed analytical queries",
                resolution="Reset connection pool and killed idle queries with graceful vacuum",
                symptoms=["DATABASE_TIMEOUT", "active_connections=500", "pool_usage=100%"],
                key_metrics={"connection_pool_usage_pct": 100.0, "query_latency_ms": 35000.0},
            ),
            HistoricalIncident(
                incident_id="HIST-INC-2026-002",
                timestamp="2026-07-22T14:40:00Z",
                affected_asset="AUTH-01",
                root_cause="JWT signature caching memory leak in release v1.14.1",
                resolution="Rolled back auth container image and increased pod memory limits",
                symptoms=["LOGIN_FAILURE", "MEMORY_WARNING", "memory_used_pct=96%"],
                key_metrics={"memory_used_pct": 96.5, "failed_auth_rate_pct": 89.0},
            ),
            HistoricalIncident(
                incident_id="HIST-INC-2026-003",
                timestamp="2026-08-05T19:00:00Z",
                affected_asset="API-01",
                root_cause="Underlying authentication service outage cascaded into ingress buffer exhaustion",
                resolution="Restarted API gateway after auth service dependency recovered",
                symptoms=["SERVICE_CRASH", "http_5xx_rate_pct=100%", "uptime_seconds=0"],
                key_metrics={"http_5xx_rate_pct": 100.0, "crash_exit_code": 137},
            ),
            HistoricalIncident(
                incident_id="HIST-INC-2026-004",
                timestamp="2026-08-14T11:20:00Z",
                affected_asset="PORTAL-01",
                root_cause="Transit ISP fiber cut causing severe packet loss and network timeout",
                resolution="Rerouted BGP traffic via secondary cloud provider edge",
                symptoms=["NETWORK_LATENCY", "p99_latency_ms=28000", "gateway_timeout_pct=100%"],
                key_metrics={"p99_latency_ms": 28000.0, "gateway_timeout_pct": 100.0},
            ),
        ])

    def find_similar_incidents(
        self,
        asset_id: str,
        event_types: Optional[List[str]] = None,
        limit: int = 3,
    ) -> List[HistoricalIncident]:
        """
        Find past incidents matching the asset or symptom keywords.
        """
        matched = []
        for inc in self._incidents:
            # Match by asset
            if inc.affected_asset == asset_id:
                matched.append(inc)
                continue

            # Match by event type in symptoms
            if event_types:
                if any(any(et.lower() in s.lower() for et in event_types) for s in inc.symptoms):
                    matched.append(inc)

        # Fallback to general history if no exact matches found
        if not matched:
            matched = list(self._incidents)

        return matched[:limit]

    def search_similar_incidents(
        self,
        signature: str,
        limit: int = 3,
    ) -> List[HistoricalIncident]:
        """
        Member 1's History API interface: search similar incidents by signature.
        """
        from digital_world.client import get_digital_world_client
        dw_records = get_digital_world_client().history.search_similar_incidents(signature, limit=limit)
        return [HistoricalIncident.model_validate(r) for r in dw_records]

    def add_incident(self, incident: HistoricalIncident) -> None:
        """Add a new resolved incident record."""
        self._incidents.append(incident)

    def get_all(self) -> List[HistoricalIncident]:
        """Retrieve all historical incident records."""
        return list(self._incidents)
