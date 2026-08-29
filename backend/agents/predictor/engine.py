"""Trend-based failure prediction and preventive recommendation engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from ...digital_world.metrics import THRESHOLDS
from ...digital_world.models import Prediction


class PredictionEngine:
    METRICS = ("cpu_percent", "memory_percent", "disk_percent", "network_latency_ms", "error_rate")

    def __init__(self, world: Any) -> None:
        self.world = world
        self.predictions: Dict[str, Prediction] = {}

    def scan(self, max_steps: float = 30.0) -> List[Dict[str, Any]]:
        created: List[Dict[str, Any]] = []
        for asset_id, asset in self.world.assets.items():
            for metric in self.METRICS:
                trend = self.world.metrics_engine.get_metric_trend(asset_id, metric, last_n=20)
                if not trend or trend["direction"] != "increasing":
                    continue
                steps = trend.get("time_to_warning_steps")
                if steps is None or steps <= 0 or steps > max_steps:
                    continue
                key = f"{asset_id}:{metric}"
                existing = self.predictions.get(key)
                if existing and not existing.acknowledged:
                    continue
                threshold = THRESHOLDS[metric]["warning"]
                prediction = Prediction(
                    prediction_id=f"PRED-{len(self.predictions) + 1:05d}",
                    asset_id=asset_id,
                    metric_name=metric,
                    current_value=trend["current"],
                    predicted_value=threshold,
                    threshold=threshold,
                    time_to_threshold_hours=round(steps * 2 / 3600, 3),
                    confidence=min(0.98, max(0.55, abs(trend["slope"]) / max(threshold, 1) * 10 + 0.55)),
                    trend_data=trend["values"],
                    created_at=datetime.now(timezone.utc),
                )
                self.predictions[key] = prediction
                created.append(prediction.model_dump(mode="json"))
        return created

    def list(self, active_only: bool = True) -> List[Dict[str, Any]]:
        predictions = list(self.predictions.values())
        if active_only:
            predictions = [prediction for prediction in predictions if not prediction.acknowledged]
        return [prediction.model_dump(mode="json") for prediction in predictions]

    def acknowledge(self, prediction_id: str) -> bool:
        for prediction in self.predictions.values():
            if prediction.prediction_id == prediction_id:
                prediction.acknowledged = True
                return True
        return False

