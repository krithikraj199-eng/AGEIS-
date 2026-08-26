"""
Metrics API for Digital World Environment.
Provides current real-time metric queries and historical metric time-series retrieval.
"""

from datetime import datetime, timezone, timedelta
import random
from typing import Any, Dict, List, Optional
from .models import MetricReading


class MetricsAPI:
    """
    Member 1's Metrics API interface:
    - get_current_metric(asset_id, metric)
    - get_historical_metrics(asset_id, metric, window_minutes)
    """

    def __init__(self):
        # In-memory baseline and live state map: (asset_id, metric) -> current_value
        self._current_metrics: Dict[str, Dict[str, float]] = {
            "DATABASE-01": {
                "latency_ms": 850.0,
                "query_latency_ms": 850.0,
                "cpu_utilization_pct": 78.5,
                "cpu_usage_pct": 78.5,
                "connection_pool_usage_pct": 98.0,
                "memory_used_pct": 82.0,
                "disk_used_pct": 75.0,
            },
            "AUTH-01": {
                "latency_ms": 420.0,
                "auth_latency_ms": 420.0,
                "cpu_utilization_pct": 65.0,
                "memory_used_pct": 91.5,
                "failed_auth_rate_pct": 14.5,
            },
            "API-01": {
                "latency_ms": 310.0,
                "cpu_utilization_pct": 55.0,
                "error_rate_pct": 4.5,
                "http_5xx_rate_pct": 5.0,
            },
            "PORTAL-01": {
                "latency_ms": 280.0,
                "portal_latency_ms": 280.0,
                "cpu_utilization_pct": 45.0,
                "p99_latency_ms": 350.0,
            },
        }
        # Historical time-series buffers: (asset_id, metric) -> list of (iso_timestamp, float_val)
        self._history_series: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self._seed_default_time_series()

    def _seed_default_time_series(self) -> None:
        """Seed initial realistic 15-minute window historical readings."""
        now = datetime.now(timezone.utc)
        for asset_id, metrics in self._current_metrics.items():
            self._history_series[asset_id] = {}
            for metric, base_val in metrics.items():
                readings = []
                for offset in range(15, 0, -1):
                    ts = (now - timedelta(minutes=offset)).isoformat()
                    # Slight variation leading up to baseline/anomaly
                    variation = (15 - offset) * (base_val * 0.03)
                    val = round(max(0.0, base_val - variation + random.uniform(-2.0, 2.0)), 2)
                    readings.append({"timestamp": ts, "value": val, "metric": metric, "asset_id": asset_id})
                self._history_series[asset_id][metric] = readings

    def get_current_metric(self, asset_id: str, metric: str) -> float:
        """
        Get the latest live metric value for a specific asset.
        If metric is not tracked, returns a deterministic fallback.
        """
        asset_map = self._current_metrics.get(asset_id, {})
        if metric in asset_map:
            return float(asset_map[metric])
        # Fallback heuristic for generic metrics
        if "latency" in metric:
            return 120.0
        if "cpu" in metric or "usage" in metric or "memory" in metric:
            return 45.0
        return 0.0

    def get_historical_metrics(
        self,
        asset_id: str,
        metric: str,
        window_minutes: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve historical metric readings across a specified time window.
        Returns list of {"timestamp": str, "value": float, "metric": str, "asset_id": str}
        """
        asset_hist = self._history_series.get(asset_id, {})
        if metric in asset_hist:
            return list(asset_hist[metric][-window_minutes:])
        
        # Synthesize historical series if not already seeded
        now = datetime.now(timezone.utc)
        current = self.get_current_metric(asset_id, metric)
        synth = []
        for i in range(window_minutes, 0, -1):
            ts = (now - timedelta(minutes=i)).isoformat()
            synth.append({
                "timestamp": ts,
                "value": round(current * (0.8 + 0.02 * (window_minutes - i)), 2),
                "metric": metric,
                "asset_id": asset_id,
            })
        return synth

    def update_metric(self, asset_id: str, metric: str, value: float) -> None:
        """Update live metric value and append to historical series."""
        if asset_id not in self._current_metrics:
            self._current_metrics[asset_id] = {}
        self._current_metrics[asset_id][metric] = float(value)

        if asset_id not in self._history_series:
            self._history_series[asset_id] = {}
        if metric not in self._history_series[asset_id]:
            self._history_series[asset_id][metric] = []
        
        self._history_series[asset_id][metric].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "value": float(value),
            "metric": metric,
            "asset_id": asset_id,
        })
