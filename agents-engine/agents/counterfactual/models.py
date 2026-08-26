"""
Counterfactual Simulation Models and Ranking Schemas for AEGIS Ω.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PlanSimulationResult(BaseModel):
    """
    Simulation evaluation for an individual candidate remediation plan:
    {
        plan_id, predicted_recovery_probability, predicted_risk,
        predicted_downtime, possible_secondary_failures
    }
    """
    plan_id: str
    predicted_recovery_probability: float = Field(
        ge=0.0,
        le=1.0,
        description="Estimated probability (0.0 to 1.0) of complete incident resolution",
    )
    predicted_risk: str = Field(
        description="Assessed operational risk category: LOW, MEDIUM, HIGH, CRITICAL",
    )
    predicted_downtime: str = Field(
        description="Estimated service disruption duration (e.g. '0s', '15s', '60s')",
    )
    possible_secondary_failures: List[str] = Field(
        default_factory=list,
        description="Potential cascading failures or side-effects predicted on downstream services",
    )
    composite_score: float = Field(
        default=0.0,
        description="Deterministic multi-criteria utility score (0.0 to 1.0)",
    )
    rank: int = Field(
        default=1,
        description="Ranking order among all evaluated candidate plans (1 = best)",
    )


class CounterfactualOutput(BaseModel):
    """
    Required output schema for Counterfactual Engine:
    {
        ranked_plans,
        selected_plan_id,
        justification
    }
    """
    incident_id: str
    correlation_id: str
    plan_id: str
    ranked_plans: List[PlanSimulationResult] = Field(
        description="Ranked list of all simulated candidate plans in descending order of optimality",
    )
    selected_plan_id: str = Field(
        description="ID of the deterministically selected highest-ranking plan",
    )
    justification: str = Field(
        description="Detailed mathematical justification explaining why the winning plan was chosen",
    )
    simulation_passed: bool = Field(
        default=True,
        description="True if at least one candidate plan satisfies safety thresholds",
    )
    predicted_side_effects: List[str] = Field(
        default_factory=list,
        description="Aggregated side-effects for the selected plan",
    )
    alternative_paths_evaluated: int = Field(
        default=1,
        description="Total number of distinct simulation scenarios evaluated",
    )
    selected_plan: Optional[Any] = None  # Full plan object for downstream execution
    simulated_at: str
