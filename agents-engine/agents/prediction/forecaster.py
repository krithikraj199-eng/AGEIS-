"""
Deterministic Trend Forecaster for AEGIS Ω Prediction Engine.
Maintains a rolling window of recent metric readings and calculates projected threshold breach time.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple

from .models import MetricReading, TrendForecast

logger = logging.getLogger(__name__)


class DeterministicTrendForecaster:
    """
    Rolling window trend analyzer and linear regression projection engine.
    100% deterministic Python calculation (zero Gemini).
    """

    # Configurable default hard thresholds across critical infrastructure metrics
    DEFAULT_THRESHOLDS: Dict[str, float] = {
        "disk_usage_pct": 90.0,
        "disk_usage": 90.0,
        "cpu_usage_pct": 90.0,
        "memory_usage_pct": 90.0,
        "connection_pool_usage_pct": 90.0,
        "query_latency_ms": 1000.0,
        "error_rate_pct": 10.0,
    }

    def __init__(
        self,
        prediction_horizon_sec: float = 180.0,
        min_window_size: int = 3,
        max_window_size: int = 15,
        thresholds: Optional[Dict[str, float]] = None,
    ):
        self.prediction_horizon_sec = prediction_horizon_sec
        self.min_window_size = min_window_size
        self.max_window_size = max_window_size
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

        # Buffer: (asset_id, metric_name) -> list of (timestamp, value)
        self._buffers: Dict[Tuple[str, str], List[Tuple[float, float]]] = {}

    def get_threshold(self, metric_name: str, override: Optional[float] = None) -> float:
        """Get hard threshold for metric."""
        if override is not None:
            return override
        return self.thresholds.get(metric_name.lower(), 90.0)

    def add_reading(
        self,
        asset_id: str,
        metric_name: str,
        value: float,
        timestamp: Optional[float] = None,
        threshold_override: Optional[float] = None,
    ) -> Optional[TrendForecast]:
        """
        Record a new metric reading and evaluate trend projection.
        Returns TrendForecast if sufficient data points exist, otherwise None.
        """
        ts = timestamp if timestamp is not None else datetime.now(timezone.utc).timestamp()
        key = (asset_id, metric_name.lower())

        if key not in self._buffers:
            self._buffers[key] = []

        self._buffers[key].append((ts, float(value)))

        # Keep within max window size
        if len(self._buffers[key]) > self.max_window_size:
            self._buffers[key] = self._buffers[key][-self.max_window_size:]

        buf = self._buffers[key]
        if len(buf) < self.min_window_size:
            return None

        # Calculate slope via linear regression
        n = len(buf)
        # Normalize time indices relative to t0 (or step index 0..N-1 if timestamps are identical)
        t0 = buf[0][0]
        t_span = buf[-1][0] - t0
        use_step_index = t_span <= 0.001  # If rapid batch insertion, use 1-second synthetic steps

        x_vals = [float(i) if use_step_index else (t - t0) for i, (t, _) in enumerate(buf)]
        y_vals = [v for _, v in buf]

        sum_x = sum(x_vals)
        sum_y = sum(y_vals)
        sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))
        sum_x2 = sum(x * x for x in x_vals)

        denominator = (n * sum_x2) - (sum_x * sum_x)
        if abs(denominator) < 1e-9:
            slope = 0.0
        else:
            slope = ((n * sum_xy) - (sum_x * sum_y)) / denominator

        current_val = y_vals[-1]
        threshold = self.get_threshold(metric_name, threshold_override)

        # Calculate projected time-to-breach
        if slope > 0 and current_val < threshold:
            # How many time units until threshold is crossed?
            delta_needed = threshold - current_val
            seconds_to_breach = delta_needed / slope
            # If step index was used, scale steps to seconds (assume 10s per reading step by default)
            if use_step_index:
                seconds_to_breach = seconds_to_breach * 10.0
        elif current_val >= threshold:
            seconds_to_breach = 0.0
        else:
            seconds_to_breach = float("inf")

        is_imminent = (0.0 <= seconds_to_breach <= self.prediction_horizon_sec) and (current_val < threshold)

        return TrendForecast(
            asset_id=asset_id,
            metric_name=metric_name,
            current_value=round(current_val, 2),
            hard_threshold=round(threshold, 2),
            slope_per_sec=round(slope, 4),
            projected_seconds_to_breach=round(seconds_to_breach, 1),
            is_breach_imminent=is_imminent,
            data_points_count=n,
        )

    def clear_buffer(self, asset_id: Optional[str] = None) -> None:
        """Clear historical readings."""
        if asset_id:
            keys_to_del = [k for k in self._buffers if k[0] == asset_id]
            for k in keys_to_del:
                del self._buffers[k]
        else:
            self._buffers.clear()
