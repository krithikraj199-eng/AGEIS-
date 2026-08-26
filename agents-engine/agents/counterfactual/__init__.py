"""
Counterfactual Agent Package for AEGIS Ω.
"""

from .models import PlanSimulationResult, CounterfactualOutput
from .simulation import (
    HistoricalActionOutcomeStore,
    SecondaryFailurePredictor,
    DeterministicPlanRanker,
)
from .agent import (
    CounterfactualAgent,
    CounterfactualInput,
    GeminiCounterfactualSimulatorProtocol,
    GeminiCounterfactualSimulator,
)

__all__ = [
    "PlanSimulationResult",
    "CounterfactualOutput",
    "HistoricalActionOutcomeStore",
    "SecondaryFailurePredictor",
    "DeterministicPlanRanker",
    "CounterfactualAgent",
    "CounterfactualInput",
    "GeminiCounterfactualSimulatorProtocol",
    "GeminiCounterfactualSimulator",
]
