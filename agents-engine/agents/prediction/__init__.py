"""
Prediction Engine Package for AEGIS Ω.
Anticipates metric crossings and triggers proactive remediation before hard failure.
"""

from .models import (
    MetricReading,
    TrendForecast,
    PredictedIncident,
    PredictionInput,
    PredictionOutput,
)
from .forecaster import DeterministicTrendForecaster
from .agent import PredictionAgent

__all__ = [
    "MetricReading",
    "TrendForecast",
    "PredictedIncident",
    "PredictionInput",
    "PredictionOutput",
    "DeterministicTrendForecaster",
    "PredictionAgent",
]
