"""
Investigator Agent Package for AEGIS Ω.
"""

from .history_store import HistoricalIncident, HistoricalIncidentStore
from .context_collector import (
    InvestigationContext,
    DeploymentRecord,
    ConfigurationRecord,
    DependencyMapRecord,
    collect_investigation_context,
)
from .hypotheses import (
    Hypothesis,
    HypothesisSet,
    EvidenceValidator,
)
from .agent import (
    InvestigatorAgent,
    InvestigatorInput,
    InvestigatorOutput,
    GeminiHypothesisGeneratorProtocol,
    GeminiHypothesisGenerator,
)

__all__ = [
    "HistoricalIncident",
    "HistoricalIncidentStore",
    "InvestigationContext",
    "DeploymentRecord",
    "ConfigurationRecord",
    "DependencyMapRecord",
    "collect_investigation_context",
    "Hypothesis",
    "HypothesisSet",
    "EvidenceValidator",
    "InvestigatorAgent",
    "InvestigatorInput",
    "InvestigatorOutput",
    "GeminiHypothesisGeneratorProtocol",
    "GeminiHypothesisGenerator",
]
