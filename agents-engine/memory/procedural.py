"""
Procedural Memory for AEGIS Ω Memory Bank.
Maintains empirical success rates for action types against incident signatures.
Implements: get_best_known_strategy(signature)
Rule: If a strategy has >80% success AND at least 3 historical incidents, bias future plan generation toward it.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .storage import ProceduralStoreProtocol, InMemoryStorageBackend

logger = logging.getLogger(__name__)


class StrategyStats(BaseModel):
    """Statistical tracking for a specific remediation strategy against a failure signature."""
    strategy: str
    success_count: int = 0
    failure_count: int = 0
    total_executions: int = 0
    success_rate: float = 0.0
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BestStrategyRecommendation(BaseModel):
    """
    Recommendation produced when a strategy meets the qualification threshold:
    >80% success rate AND >= 3 historical incidents.
    """
    signature: str
    recommended_strategy: str
    success_rate: float
    total_incidents: int
    confidence_boost: float = 0.15
    rationale: str


class ProceduralMemory:
    """
    Procedural Memory Engine for AEGIS Ω.
    Tracks empirical outcomes and biases Planner towards historically proven strategies.
    """

    # Qualification criteria thresholds
    MIN_SUCCESS_RATE: float = 0.80  # >80%
    MIN_INCIDENT_COUNT: int = 3     # at least 3 historical incidents

    def __init__(self, store: Optional[ProceduralStoreProtocol] = None):
        self.store = store or InMemoryStorageBackend()

    def record_action_outcome(
        self,
        signature: str,
        strategy: str,
        success: bool,
    ) -> StrategyStats:
        """
        Record a remediation outcome.
        When an action successfully resolves an incident: increase its success count.
        """
        raw_stat = self.store.record_outcome(signature=signature, strategy=strategy, success=success)
        stat = StrategyStats.model_validate(raw_stat)
        logger.info(
            f"Procedural Memory updated for signature '{signature}' | strategy '{strategy}': "
            f"success={success} (Rate: {stat.success_rate * 100:.1f}%, Total: {stat.total_executions})."
        )
        return stat

    def get_strategy_stats(self, signature: str) -> Dict[str, StrategyStats]:
        """Get all strategy statistics for a specific signature."""
        raw_dict = self.store.get_strategy_stats(signature)
        return {k: StrategyStats.model_validate(v) for k, v in raw_dict.items()}

    def get_best_known_strategy(self, signature: str) -> Optional[BestStrategyRecommendation]:
        """
        Retrieve best-known strategy for an incident signature if it qualifies:
          1. Success rate > 80% (>0.80)
          2. Total executions >= 3
        """
        stats_map = self.get_strategy_stats(signature)
        if not stats_map:
            return None

        qualifying_candidates: List[StrategyStats] = []

        for stat in stats_map.values():
            if stat.total_executions >= self.MIN_INCIDENT_COUNT and stat.success_rate > self.MIN_SUCCESS_RATE:
                qualifying_candidates.append(stat)

        if not qualifying_candidates:
            return None

        # Sort by highest success rate, then total executions
        qualifying_candidates.sort(key=lambda s: (s.success_rate, s.total_executions), reverse=True)
        best = qualifying_candidates[0]

        rationale = (
            f"Procedural Memory match for signature '{signature}': strategy '{best.strategy}' "
            f"has demonstrated {best.success_rate * 100:.1f}% success rate across {best.total_executions} "
            f"historical incidents (qualifies with >80% success and >=3 incidents)."
        )

        return BestStrategyRecommendation(
            signature=signature,
            recommended_strategy=best.strategy,
            success_rate=best.success_rate,
            total_incidents=best.total_executions,
            confidence_boost=0.15,
            rationale=rationale,
        )

    def clear(self) -> None:
        """Clear all procedural memory records."""
        if hasattr(self.store, "clear"):
            self.store.clear()
