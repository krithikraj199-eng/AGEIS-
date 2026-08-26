"""
Evidence Agent Package for AEGIS Ω.
"""

from .delta_engine import (
    MetricDelta,
    STANDARD_BASELINES,
    calculate_metric_delta,
    HistoricalSimilarityScorer,
)
from .models import EvidenceItem, EvidenceOutput
from .agent import (
    EvidenceAgent,
    EvidenceInput,
    GeminiEvidenceSummarizerProtocol,
    GeminiEvidenceSummarizer,
)

__all__ = [
    "MetricDelta",
    "STANDARD_BASELINES",
    "calculate_metric_delta",
    "HistoricalSimilarityScorer",
    "EvidenceItem",
    "EvidenceOutput",
    "EvidenceAgent",
    "EvidenceInput",
    "GeminiEvidenceSummarizerProtocol",
    "GeminiEvidenceSummarizer",
]
