"""
History API for Digital World Environment.
Provides historical incident signature search and past resolution lookup.
"""

from typing import Any, Dict, List, Optional
from .models import HistoricalIncidentRecord


class HistoryAPI:
    """
    Member 1's History API interface:
    - search_similar_incidents(signature) -> search incidents matching signature (e.g. DATABASE-01:DATABASE_TIMEOUT)
    """

    def __init__(self):
        self._incidents: List[HistoricalIncidentRecord] = []
        self._seed_default_history()

    def _seed_default_history(self) -> None:
        """Seed realistic historical incident catalog."""
        self._incidents.extend([
            HistoricalIncidentRecord(
                incident_id="HIST-INC-2026-001",
                timestamp="2026-07-10T08:15:00Z",
                signature="DATABASE-01:DATABASE_TIMEOUT",
                affected_asset="DATABASE-01",
                root_cause="Postgres connection pool exhaustion caused by unindexed analytical queries",
                resolution="Scaled connection pool replicas and killed idle queries with graceful vacuum",
                symptoms=["DATABASE_TIMEOUT", "active_connections=500", "pool_usage=100%"],
                key_metrics={"connection_pool_usage_pct": 100.0, "query_latency_ms": 35000.0},
            ),
            HistoricalIncidentRecord(
                incident_id="HIST-INC-2026-002",
                timestamp="2026-07-22T14:40:00Z",
                signature="AUTH-01:LOGIN_FAILURE",
                affected_asset="AUTH-01",
                root_cause="JWT signature caching memory leak in release v1.14.1",
                resolution="Rolled back auth container image and increased pod memory limits",
                symptoms=["LOGIN_FAILURE", "MEMORY_WARNING", "memory_used_pct=96%"],
                key_metrics={"memory_used_pct": 96.5, "failed_auth_rate_pct": 89.0},
            ),
            HistoricalIncidentRecord(
                incident_id="HIST-INC-2026-003",
                timestamp="2026-08-05T19:00:00Z",
                signature="API-01:SERVICE_CRASH",
                affected_asset="API-01",
                root_cause="Underlying authentication service outage cascaded into ingress buffer exhaustion",
                resolution="Restarted API gateway after auth service dependency recovered",
                symptoms=["SERVICE_CRASH", "http_5xx_rate_pct=100%", "uptime_seconds=0"],
                key_metrics={"http_5xx_rate_pct": 100.0, "crash_exit_code": 137},
            ),
            HistoricalIncidentRecord(
                incident_id="HIST-INC-2026-004",
                timestamp="2026-08-14T11:20:00Z",
                signature="PORTAL-01:NETWORK_LATENCY",
                affected_asset="PORTAL-01",
                root_cause="Transit ISP fiber cut causing severe packet loss and network timeout",
                resolution="Rerouted BGP traffic via secondary cloud provider edge and cleared edge cache",
                symptoms=["NETWORK_LATENCY", "p99_latency_ms=28000", "gateway_timeout_pct=100%"],
                key_metrics={"p99_latency_ms": 28000.0, "gateway_timeout_pct": 100.0},
            ),
        ])

    def search_similar_incidents(
        self,
        signature: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search for past incidents matching an incident signature (or asset / event type).
        Returns list of serialized incident dictionaries.
        """
        sig_lower = signature.lower()
        matched: List[HistoricalIncidentRecord] = []

        # 1. Exact signature match
        for inc in self._incidents:
            if inc.signature.lower() == sig_lower:
                matched.append(inc)

        # 2. Asset match
        if len(matched) < limit:
            for inc in self._incidents:
                if inc not in matched and inc.affected_asset.lower() in sig_lower:
                    matched.append(inc)

        # 3. Symptom or keyword match
        if len(matched) < limit:
            for inc in self._incidents:
                if inc not in matched:
                    if any(s.lower() in sig_lower for s in inc.symptoms):
                        matched.append(inc)

        # 4. Fallback to all incidents
        if not matched:
            matched = list(self._incidents)

        return [m.model_dump() for m in matched[:limit]]

    def add_incident(self, record: HistoricalIncidentRecord) -> None:
        """Add a newly resolved incident into historical storage."""
        self._incidents.append(record)
