"""
AEGIS Ω — Metrics Engine

Handles realistic fluctuation of asset metrics over time.
Provides deterministic threshold checks for the Sentinel
so we don't waste LLM calls on obvious numerical comparisons.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .models import Asset, AssetMetrics, AssetStatus, AssetType, Severity


# ═══════════════════════════════════════════════════════════
# THRESHOLDS
# ═══════════════════════════════════════════════════════════

THRESHOLDS = {
    "cpu_percent": {"warning": 75, "critical": 90},
    "memory_percent": {"warning": 80, "critical": 95},
    "disk_percent": {"warning": 80, "critical": 95},
    "network_latency_ms": {"warning": 100, "critical": 500},
    "error_rate": {"warning": 5, "critical": 15},
    "response_time_ms": {"warning": 500, "critical": 2000},
    "connection_count": {"warning": 800, "critical": 950},
    "queue_depth": {"warning": 50, "critical": 100},
}


class MetricsEngine:
    """
    Updates asset metrics with realistic drift, noise, and
    diurnal patterns.  Provides threshold-based alerting.
    """

    def __init__(self):
        self.history: Dict[str, List[Dict[str, Any]]] = {}  # asset_id → metric snapshots
        self.max_history = 500  # per asset

    # ──────────────────────────────────────────────────────
    # NATURAL DRIFT
    # ──────────────────────────────────────────────────────

    def update_metrics_naturally(self, asset: Asset, sim_hour: int = 12) -> AssetMetrics:
        """
        Apply small, realistic fluctuations influenced by time of day.
        9–17 = busier, 22–6 = quieter.
        """
        m = asset.metrics
        load_factor = self._diurnal_factor(sim_hour)

        m.cpu_percent = self._drift(m.cpu_percent, -3, 3, 0, 100, load_factor)
        m.memory_percent = self._drift(m.memory_percent, -1, 2, 0, 100, load_factor)
        m.disk_percent = self._drift(m.disk_percent, 0, 0.1, 0, 100)  # slow growth
        m.network_latency_ms = self._drift(m.network_latency_ms, -2, 2, 0.5, 2000, load_factor)
        m.error_rate = self._drift(m.error_rate, -0.5, 0.5, 0, 100, load_factor)
        m.request_rate = self._drift(m.request_rate, -20, 20, 0, 10000, load_factor)
        m.connection_count = int(self._drift(m.connection_count, -5, 5, 0, 5000, load_factor))
        m.response_time_ms = self._drift(m.response_time_ms, -5, 5, 1, 10000, load_factor)
        m.throughput = self._drift(m.throughput, -10, 10, 0, 50000, load_factor)
        m.queue_depth = max(0, int(self._drift(m.queue_depth, -2, 2, 0, 500, load_factor)))
        m.uptime_seconds += random.randint(1, 5)

        # Update asset status from metrics
        asset.status = self._derive_status(m)
        asset.metrics = m

        # Record history
        self._record(asset.asset_id, m)

        return m

    # ──────────────────────────────────────────────────────
    # APPLY STRESS (used by Chaos Engine)
    # ──────────────────────────────────────────────────────

    def apply_stress(self, asset: Asset, stress_type: str,
                     intensity: float = 1.0) -> AssetMetrics:
        """
        Apply a specific stress to an asset's metrics.
        intensity: 0.0 – 1.0 (how severe)
        """
        m = asset.metrics
        mult = 0.3 + intensity * 0.7  # scale 0.3x – 1.0x

        if stress_type == "cpu_spike":
            m.cpu_percent = min(100, m.cpu_percent + 40 * mult + random.uniform(0, 15))
        elif stress_type == "memory_leak":
            m.memory_percent = min(100, m.memory_percent + 25 * mult + random.uniform(0, 10))
        elif stress_type == "disk_exhaustion":
            m.disk_percent = min(100, m.disk_percent + 20 * mult + random.uniform(0, 8))
        elif stress_type == "network_latency":
            m.network_latency_ms = m.network_latency_ms + 200 * mult + random.uniform(0, 100)
        elif stress_type == "connection_flood":
            m.connection_count = int(m.connection_count + 500 * mult + random.randint(0, 200))
        elif stress_type == "error_spike":
            m.error_rate = min(100, m.error_rate + 20 * mult + random.uniform(0, 10))
        elif stress_type == "response_degradation":
            m.response_time_ms = m.response_time_ms + 800 * mult + random.uniform(0, 400)
        elif stress_type == "queue_backup":
            m.queue_depth = int(m.queue_depth + 80 * mult + random.randint(0, 30))
        elif stress_type == "throughput_drop":
            m.throughput = max(0, m.throughput * (1 - 0.6 * mult))

        asset.status = self._derive_status(m)
        asset.metrics = m
        self._record(asset.asset_id, m)
        return m

    def relieve_stress(self, asset: Asset, stress_type: str,
                       recovery_pct: float = 0.7) -> AssetMetrics:
        """Partially or fully recover from stress."""
        m = asset.metrics
        if stress_type == "cpu_spike":
            m.cpu_percent = max(15, m.cpu_percent * (1 - recovery_pct) + random.uniform(5, 15))
        elif stress_type == "memory_leak":
            m.memory_percent = max(25, m.memory_percent * (1 - recovery_pct) + random.uniform(5, 15))
        elif stress_type == "disk_exhaustion":
            m.disk_percent = max(20, m.disk_percent * (1 - recovery_pct) + random.uniform(5, 10))
        elif stress_type == "network_latency":
            m.network_latency_ms = max(1, m.network_latency_ms * (1 - recovery_pct) + random.uniform(1, 5))
        elif stress_type == "connection_flood":
            m.connection_count = max(20, int(m.connection_count * (1 - recovery_pct)))
        elif stress_type == "error_spike":
            m.error_rate = max(0, m.error_rate * (1 - recovery_pct))
        elif stress_type == "response_degradation":
            m.response_time_ms = max(5, m.response_time_ms * (1 - recovery_pct) + random.uniform(5, 20))
        elif stress_type == "queue_backup":
            m.queue_depth = max(0, int(m.queue_depth * (1 - recovery_pct)))
        elif stress_type == "throughput_drop":
            m.throughput = m.throughput / max(0.01, (1 - recovery_pct * 0.5))

        asset.status = self._derive_status(m)
        asset.metrics = m
        self._record(asset.asset_id, m)
        return m

    # ──────────────────────────────────────────────────────
    # THRESHOLD CHECKS (deterministic — no LLM needed)
    # ──────────────────────────────────────────────────────

    def check_thresholds(self, asset: Asset) -> List[Dict[str, Any]]:
        """
        Run all deterministic threshold checks.
        Returns list of alerts (may be empty).
        """
        alerts: List[Dict[str, Any]] = []
        m = asset.metrics

        for metric_name, levels in THRESHOLDS.items():
            value = getattr(m, metric_name, None)
            if value is None:
                continue

            warning = levels["warning"]
            critical = levels["critical"]

            if value >= critical:
                alerts.append({
                    "asset_id": asset.asset_id,
                    "metric": metric_name,
                    "value": round(value, 2),
                    "threshold": critical,
                    "severity": "critical",
                    "message": f"{metric_name} at {value:.1f} exceeds critical threshold {critical}",
                })
            elif value >= warning:
                alerts.append({
                    "asset_id": asset.asset_id,
                    "metric": metric_name,
                    "value": round(value, 2),
                    "threshold": warning,
                    "severity": "warning",
                    "message": f"{metric_name} at {value:.1f} exceeds warning threshold {warning}",
                })

        return alerts

    # ──────────────────────────────────────────────────────
    # TREND DETECTION (for Prediction Engine)
    # ──────────────────────────────────────────────────────

    def get_metric_trend(self, asset_id: str, metric_name: str,
                         last_n: int = 20) -> Optional[Dict[str, Any]]:
        """
        Detect trends in a metric over the last N snapshots.
        Returns slope, direction, and predicted time to threshold.
        """
        history = self.history.get(asset_id, [])
        if len(history) < 5:
            return None

        values = []
        for snap in history[-last_n:]:
            val = snap.get(metric_name)
            if val is not None:
                values.append(val)

        if len(values) < 5:
            return None

        # Simple linear regression
        n = len(values)
        x = list(range(n))
        mean_x = sum(x) / n
        mean_y = sum(values) / n
        ss_xy = sum((x[i] - mean_x) * (values[i] - mean_y) for i in range(n))
        ss_xx = sum((x[i] - mean_x) ** 2 for i in range(n))

        if ss_xx == 0:
            return None

        slope = ss_xy / ss_xx
        direction = "increasing" if slope > 0.1 else "decreasing" if slope < -0.1 else "stable"

        # Time to threshold
        thresholds = THRESHOLDS.get(metric_name)
        time_to_warning = None
        time_to_critical = None

        if thresholds and slope > 0.1:
            current = values[-1]
            if current < thresholds["warning"]:
                steps = (thresholds["warning"] - current) / slope
                time_to_warning = steps
            if current < thresholds["critical"]:
                steps = (thresholds["critical"] - current) / slope
                time_to_critical = steps

        return {
            "metric": metric_name,
            "values": values[-10:],
            "current": round(values[-1], 2),
            "slope": round(slope, 4),
            "direction": direction,
            "time_to_warning_steps": round(time_to_warning, 1) if time_to_warning else None,
            "time_to_critical_steps": round(time_to_critical, 1) if time_to_critical else None,
        }

    # ──────────────────────────────────────────────────────
    # HISTORY
    # ──────────────────────────────────────────────────────

    def get_history(self, asset_id: str, last_n: int = 50) -> List[Dict[str, Any]]:
        return self.history.get(asset_id, [])[-last_n:]

    # ──────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────

    def _drift(self, current: float, min_delta: float, max_delta: float,
               floor: float, ceiling: float,
               load_factor: float = 1.0) -> float:
        delta = random.uniform(min_delta, max_delta) * load_factor
        # Add random noise
        delta += random.gauss(0, 0.5)
        value = current + delta
        return max(floor, min(ceiling, value))

    @staticmethod
    def _diurnal_factor(hour: int) -> float:
        """Simulate day/night load pattern. Peak at ~12, trough at ~3."""
        return 0.5 + 0.5 * math.sin(math.pi * (hour - 6) / 12)

    @staticmethod
    def _derive_status(m: AssetMetrics) -> AssetStatus:
        """Derive overall asset status from metrics."""
        critical_count = 0
        warning_count = 0

        for metric_name, levels in THRESHOLDS.items():
            val = getattr(m, metric_name, None)
            if val is None:
                continue
            if val >= levels["critical"]:
                critical_count += 1
            elif val >= levels["warning"]:
                warning_count += 1

        if critical_count >= 2:
            return AssetStatus.CRITICAL
        elif critical_count >= 1:
            return AssetStatus.WARNING
        elif warning_count >= 2:
            return AssetStatus.DEGRADED
        elif warning_count >= 1:
            return AssetStatus.WARNING
        return AssetStatus.HEALTHY

    def _record(self, asset_id: str, m: AssetMetrics):
        if asset_id not in self.history:
            self.history[asset_id] = []

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": round(m.cpu_percent, 2),
            "memory_percent": round(m.memory_percent, 2),
            "disk_percent": round(m.disk_percent, 2),
            "network_latency_ms": round(m.network_latency_ms, 2),
            "error_rate": round(m.error_rate, 2),
            "request_rate": round(m.request_rate, 2),
            "connection_count": m.connection_count,
            "response_time_ms": round(m.response_time_ms, 2),
            "throughput": round(m.throughput, 2),
            "queue_depth": m.queue_depth,
        }
        self.history[asset_id].append(snapshot)

        # Trim
        if len(self.history[asset_id]) > self.max_history:
            self.history[asset_id] = self.history[asset_id][-self.max_history:]
