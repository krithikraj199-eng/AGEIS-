"""
Deterministic Metric Delta Engine and Historical Similarity Scorer for AEGIS Ω Evidence Agent.
Pure Python mathematical calculations. Gemini NEVER computes numbers.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from agents.investigator.history_store import HistoricalIncident, HistoricalIncidentStore


# Standard nominal baseline values for infrastructure metrics
STANDARD_BASELINES: Dict[str, float] = {
    "query_latency_ms": 15.0,
    "connection_pool_usage_pct": 20.0,
    "cpu_utilization_pct": 25.0,
    "memory_used_pct": 45.0,
    "disk_used_pct": 40.0,
    "p99_latency_ms": 50.0,
    "failed_auth_rate_pct": 0.5,
    "http_5xx_rate_pct": 0.1,
    "active_connections": 50.0,
    "deadlocks": 0.0,
    "gateway_timeout_pct": 0.0,
    "packet_loss_pct": 0.0,
}


class MetricDelta(BaseModel):
    """Calculated metric delta record."""
    metric_name: str
    before_value: float
    after_value: float
    absolute_change: float
    percentage_change: float
    formatted_delta: str
    asset_id: str
    source: str


def calculate_metric_delta(
    metric_name: str,
    before: float,
    after: float,
    asset_id: str = "SYSTEM",
    source: str = "telemetry_collector",
) -> MetricDelta:
    """
    Deterministically compute absolute and percentage changes in pure Python.
    Gemini must NEVER calculate these numbers.
    """
    before_val = float(before)
    after_val = float(after)
    abs_change = round(after_val - before_val, 4)

    if before_val != 0.0:
        pct_change = round(((after_val - before_val) / abs(before_val)) * 100.0, 2)
    else:
        pct_change = 100.0 if after_val > 0.0 else (-100.0 if after_val < 0.0 else 0.0)

    sign = "+" if pct_change > 0 else ""
    formatted = f"{sign}{pct_change:.1f}%"

    return MetricDelta(
        metric_name=metric_name,
        before_value=before_val,
        after_value=after_val,
        absolute_change=abs_change,
        percentage_change=pct_change,
        formatted_delta=formatted,
        asset_id=asset_id,
        source=source,
    )


class HistoricalSimilarityScorer:
    """
    Computes deterministic similarity score (0.0 to 1.0) between current observed anomalies
    and historical incident store records.
    """

    def __init__(self, history_store: Optional[HistoricalIncidentStore] = None):
        self.history_store = history_store or HistoricalIncidentStore()

    def calculate_similarity(
        self,
        asset_id: str,
        observed_metrics: Dict[str, Any],
        observed_events: List[str],
    ) -> float:
        """
        Calculate normalized similarity score against historical incidents.
        """
        historical = self.history_store.get_all()
        if not historical:
            return 0.0

        max_score = 0.0
        current_metric_keys = set(k.lower() for k in observed_metrics.keys())
        current_events_set = set(e.upper() for e in observed_events)

        for inc in historical:
            score = 0.0

            # Asset match bonus (0.35)
            if inc.affected_asset == asset_id:
                score += 0.35

            # Symptom / Event overlap (0.35)
            inc_symptoms = set(s.upper() for s in inc.symptoms)
            overlap_events = len(current_events_set.intersection(inc_symptoms))
            if overlap_events > 0:
                score += min(0.35, overlap_events * 0.20)

            # Metric key overlap (0.30)
            inc_metrics = set(k.lower() for k in inc.key_metrics.keys())
            if current_metric_keys and inc_metrics:
                overlap_metrics = len(current_metric_keys.intersection(inc_metrics))
                jaccard = overlap_metrics / len(current_metric_keys.union(inc_metrics))
                score += jaccard * 0.30

            if score > max_score:
                max_score = score

        return round(min(1.0, max_score), 2)
