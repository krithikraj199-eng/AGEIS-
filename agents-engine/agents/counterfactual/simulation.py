"""
Simulation Engine, Historical Outcome Registry, and Deterministic Plan Ranker for AEGIS Ω.
Enforces strictly deterministic plan ranking and secondary failure prediction.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from .models import PlanSimulationResult


class HistoricalActionOutcomeStore:
    """
    Historical outcome benchmarks for remediation tool actions.
    Tracks historical recovery probability, risk baseline, and downtime profile.
    """

    DEFAULT_TOOL_BENCHMARKS: Dict[str, Dict[str, Any]] = {
        "scale_service": {
            "base_recovery_prob": 0.94,
            "base_risk": "LOW",
            "base_downtime": "0s",
        },
        "restore_configuration": {
            "base_recovery_prob": 0.91,
            "base_risk": "LOW",
            "base_downtime": "0s",
        },
        "rollback_deployment": {
            "base_recovery_prob": 0.88,
            "base_risk": "LOW",
            "base_downtime": "5s",
        },
        "restart_service": {
            "base_recovery_prob": 0.82,
            "base_risk": "MEDIUM",
            "base_downtime": "15s",
        },
        "clear_cache": {
            "base_recovery_prob": 0.78,
            "base_risk": "MEDIUM",
            "base_downtime": "0s",
        },
        "quarantine_asset": {
            "base_recovery_prob": 0.75,
            "base_risk": "HIGH",
            "base_downtime": "60s",
        },
    }

    @classmethod
    def get_benchmark(cls, tool_name: str) -> Dict[str, Any]:
        return cls.DEFAULT_TOOL_BENCHMARKS.get(
            tool_name,
            {"base_recovery_prob": 0.70, "base_risk": "MEDIUM", "base_downtime": "30s"},
        )


class SecondaryFailurePredictor:
    """
    Predicts potential side-effects and secondary failures based on tool type and asset dependencies.
    """

    @classmethod
    def predict_side_effects(
        cls,
        strategy: str,
        target_asset: str,
        affected_systems: List[str],
    ) -> List[str]:
        """Model realistic cascading failure risks during remediation execution."""
        strat = strategy.lower().strip()
        effects = []

        if "restart" in strat:
            effects.append(f"Transient connection timeout on downstream dependents while {target_asset} recycles.")
        elif "cache" in strat:
            effects.append(f"Potential cache stampede / backend query latency spike on database tier.")
        elif "scale" in strat:
            effects.append(f"Increased memory and network utilization on host during container replica warmup.")
        elif "rollback" in strat:
            effects.append(f"Transient schema incompatibility for in-flight requests during rolling deployment revert.")
        elif "quarantine" in strat:
            effects.append(f"Downstream 503 error rate spike until failover load balancers stabilize routing.")
        elif "restore" in strat or "config" in strat:
            effects.append(f"Brief connection pool re-initialization during configuration daemon reload.")

        return effects


class DeterministicPlanRanker:
    """
    Deterministic Multi-Criteria Ranking Algorithm in pure Python.
    Strict Priority Weighting:
      1. Recovery Probability (Weight: 0.50)
      2. Operational Risk (Weight: 0.30)
      3. Downtime Disruption (Weight: 0.20)
    Gemini is strictly forbidden from choosing the final winning plan.
    """

    WEIGHT_RECOVERY = 0.50
    WEIGHT_RISK = 0.30
    WEIGHT_DOWNTIME = 0.20

    RISK_SCORES = {
        "LOW": 1.0,
        "MEDIUM": 0.65,
        "HIGH": 0.30,
        "CRITICAL": 0.0,
    }

    @classmethod
    def _parse_downtime_score(cls, downtime_str: str) -> float:
        """Convert downtime duration string to normalized score (0.0 to 1.0, higher is better)."""
        dt = downtime_str.lower().strip()
        if "0s" in dt or "zero" in dt or "none" in dt:
            return 1.0

        # Extract digits in seconds
        match = re.search(r"(\d+)", dt)
        if match:
            secs = float(match.group(1))
            if secs <= 5:
                return 0.90
            elif secs <= 15:
                return 0.75
            elif secs <= 30:
                return 0.55
            elif secs <= 60:
                return 0.35
            else:
                return 0.10

        return 0.50

    @classmethod
    def calculate_plan_score(
        cls,
        recovery_prob: float,
        risk_str: str,
        downtime_str: str,
    ) -> float:
        """
        Compute deterministic multi-criteria score in [0.0, 1.0].
        Score = 0.50 * P(rec) + 0.30 * S(risk) + 0.20 * S(downtime)
        """
        p_rec = min(1.0, max(0.0, float(recovery_prob)))
        s_risk = cls.RISK_SCORES.get(risk_str.upper(), 0.50)
        s_down = cls._parse_downtime_score(downtime_str)

        composite = (
            (cls.WEIGHT_RECOVERY * p_rec)
            + (cls.WEIGHT_RISK * s_risk)
            + (cls.WEIGHT_DOWNTIME * s_down)
        )
        return round(composite, 4)

    @classmethod
    def rank_plans(
        cls,
        simulation_results: List[PlanSimulationResult],
    ) -> Tuple[List[PlanSimulationResult], str, str]:
        """
        Rank all simulated candidate plans descending by composite score.
        Returns (ranked_plans, selected_plan_id, justification).
        """
        if not simulation_results:
            raise ValueError("Cannot rank empty simulation results list.")

        # Compute composite scores
        for res in simulation_results:
            res.composite_score = cls.calculate_plan_score(
                recovery_prob=res.predicted_recovery_probability,
                risk_str=res.predicted_risk,
                downtime_str=res.predicted_downtime,
            )

        # Sort descending by composite score, breaking ties by recovery probability
        sorted_results = sorted(
            simulation_results,
            key=lambda x: (x.composite_score, x.predicted_recovery_probability),
            reverse=True,
        )

        # Assign ranks
        for idx, res in enumerate(sorted_results, start=1):
            res.rank = idx

        winner = sorted_results[0]

        justification = (
            f"Selected plan '{winner.plan_id}' with top deterministic score {winner.composite_score:.4f} "
            f"[Recovery Prob: {winner.predicted_recovery_probability:.0%}, Risk: {winner.predicted_risk}, "
            f"Downtime: {winner.predicted_downtime}]. Evaluated {len(sorted_results)} candidate paths."
        )

        return sorted_results, winner.plan_id, justification
