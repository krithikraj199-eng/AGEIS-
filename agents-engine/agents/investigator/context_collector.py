"""
Investigation Context Collector for AEGIS Ω Investigator Agent.
Aggregates multi-dimensional telemetry, deployment changes, configuration diffs,
topological dependencies, and historical incidents.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .history_store import HistoricalIncident, HistoricalIncidentStore


class DeploymentRecord(BaseModel):
    """Recent CI/CD deployment or container update."""
    asset_id: str
    deployed_version: str
    previous_version: str
    deployed_at: str
    deployed_by: str
    change_summary: str


class ConfigurationRecord(BaseModel):
    """Recent configuration or environment parameter change."""
    asset_id: str
    config_key: str
    previous_value: Any
    current_value: Any
    updated_at: str


class DependencyMapRecord(BaseModel):
    """Topology mapping of upstream and downstream asset links."""
    asset_id: str
    upstream_assets: List[str] = Field(default_factory=list)
    downstream_assets: List[str] = Field(default_factory=list)


class InvestigationContext(BaseModel):
    """
    Comprehensive context package gathered for hypothesis generation.
    All evidence cited by Gemini must be grounded in these records.
    """
    incident_id: str
    correlation_id: str
    primary_asset_id: str
    recent_events: List[Dict[str, Any]] = Field(default_factory=list)
    recent_metrics: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    configuration_changes: List[ConfigurationRecord] = Field(default_factory=list)
    deployment_changes: List[DeploymentRecord] = Field(default_factory=list)
    dependency_information: Dict[str, DependencyMapRecord] = Field(default_factory=dict)
    historical_incidents: List[HistoricalIncident] = Field(default_factory=list)


def collect_investigation_context(
    incident_id: str,
    correlation_id: str,
    asset_id: str,
    triggering_events: List[Dict[str, Any]],
    history_store: Optional[HistoricalIncidentStore] = None,
) -> InvestigationContext:
    """
    Assemble complete investigation context across all infrastructure dimensions.
    """
    store = history_store or HistoricalIncidentStore()

    # 1. Recent Events
    events = list(triggering_events) if triggering_events else []

    # 2. Extract metrics per asset from events
    recent_metrics: Dict[str, Dict[str, Any]] = {}
    event_types = []
    for ev in events:
        aid = ev.get("asset_id", asset_id)
        etype = ev.get("event_type", "UNKNOWN")
        event_types.append(etype)
        metrics = ev.get("metrics", {})
        if aid not in recent_metrics:
            recent_metrics[aid] = {}
        recent_metrics[aid].update(metrics)

    # 3. Simulated Configuration Changes
    configs = [
        ConfigurationRecord(
            asset_id="DATABASE-01",
            config_key="max_connections",
            previous_value=800,
            current_value=500,
            updated_at="2026-08-25T12:00:00Z",
        ),
        ConfigurationRecord(
            asset_id="AUTH-01",
            config_key="token_timeout_seconds",
            previous_value=30,
            current_value=10,
            updated_at="2026-08-25T12:30:00Z",
        ),
    ]

    # 4. Simulated Deployment Changes
    deployments = [
        DeploymentRecord(
            asset_id="AUTH-01",
            deployed_version="v2.1.0-patch",
            previous_version="v2.0.8",
            deployed_at="2026-08-25T13:00:00Z",
            deployed_by="ci-cd-pipeline",
            change_summary="Upgraded JWT auth verification algorithm",
        ),
        DeploymentRecord(
            asset_id="API-01",
            deployed_version="v3.4.1",
            previous_version="v3.4.0",
            deployed_at="2026-08-25T11:15:00Z",
            deployed_by="ci-cd-pipeline",
            change_summary="Refactored request ingress routing",
        ),
    ]

    # 5. Topological Dependency Information
    dependencies = {
        "DATABASE-01": DependencyMapRecord(
            asset_id="DATABASE-01",
            upstream_assets=[],
            downstream_assets=["AUTH-01", "API-01", "PORTAL-01"],
        ),
        "AUTH-01": DependencyMapRecord(
            asset_id="AUTH-01",
            upstream_assets=["DATABASE-01"],
            downstream_assets=["API-01", "PORTAL-01"],
        ),
        "API-01": DependencyMapRecord(
            asset_id="API-01",
            upstream_assets=["AUTH-01"],
            downstream_assets=["PORTAL-01"],
        ),
        "PORTAL-01": DependencyMapRecord(
            asset_id="PORTAL-01",
            upstream_assets=["API-01"],
            downstream_assets=[],
        ),
    }

    # 6. Historical Incidents
    history = store.find_similar_incidents(asset_id=asset_id, event_types=event_types, limit=3)

    return InvestigationContext(
        incident_id=incident_id,
        correlation_id=correlation_id,
        primary_asset_id=asset_id,
        recent_events=events,
        recent_metrics=recent_metrics,
        configuration_changes=configs,
        deployment_changes=deployments,
        dependency_information=dependencies,
        historical_incidents=history,
    )
