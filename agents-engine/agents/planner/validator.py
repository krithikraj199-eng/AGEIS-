"""
Plan Validation and Deterministic Remediation Strategy Generators for AEGIS Ω.
Strictly validates allowed tool whitelist, rollback presence, and strategy diversity.
"""

import logging
from typing import Any, Dict, List, Optional
from pydantic import ValidationError

from .models import (
    ALLOWED_TOOL_NAMES,
    AllowedTool,
    RemediationAction,
    RemediationPlan,
)

logger = logging.getLogger(__name__)


class PlanValidator:
    """
    Validates LLM-generated remediation plans against the strict tool whitelist.
    Ensures 2-4 distinct strategies and mandatory rollback procedures.
    """

    @classmethod
    def generate_deterministic_plans(
        cls,
        target_asset: str,
        blast_radius: Any,
        correlation_id: str,
    ) -> List[RemediationPlan]:
        """
        Generate 3 distinct verified fallback remediation plans.
        """
        short_id = correlation_id[:8]

        # Plan 1: Scale Service (Horizontal/Pool Scaling)
        plan_scale = RemediationPlan(
            plan_id=f"PLAN-{short_id}-SCALE",
            name=f"Scale Connection Pool & Replicas on {target_asset}",
            strategy="scale",
            actions=[
                RemediationAction(
                    step=1,
                    tool=AllowedTool.SCALE_SERVICE.value,
                    target_asset=target_asset,
                    parameters={"asset_id": target_asset, "factor": 2.0, "replicas": 3},
                )
            ],
            expected_result=f"Alleviate connection starvation on {target_asset} by provisioning additional capacity",
            estimated_recovery_seconds=45,
            risk_estimate="LOW",
            downtime_estimate="Zero downtime (hot scaling)",
            blast_radius=blast_radius or "Local asset capacity expansion",
            confidence=92,
            rollback_method=f"Scale back {target_asset} to baseline replica count if resource consumption exceeds limit.",
        )

        # Plan 2: Restart Service (Graceful Process Recycle)
        plan_restart = RemediationPlan(
            plan_id=f"PLAN-{short_id}-RESTART",
            name=f"Graceful Service Recycle for {target_asset}",
            strategy="restart",
            actions=[
                RemediationAction(
                    step=1,
                    tool=AllowedTool.RESTART_SERVICE.value,
                    target_asset=target_asset,
                    parameters={"asset_id": target_asset, "grace_period_seconds": 15},
                )
            ],
            expected_result=f"Clear active deadlock state and reset thread pool on {target_asset}",
            estimated_recovery_seconds=30,
            risk_estimate="MEDIUM",
            downtime_estimate="~10 seconds during graceful drain",
            blast_radius=blast_radius or "Transient latency spike on downstream dependents",
            confidence=85,
            rollback_method=f"Rollback to standby replica or restore secondary instance if {target_asset} fails to re-register.",
        )

        # Plan 3: Rollback Deployment (Revert to Known Stable Release)
        plan_rollback = RemediationPlan(
            plan_id=f"PLAN-{short_id}-ROLLBACK",
            name=f"Rollback {target_asset} to Previous Stable Release",
            strategy="rollback",
            actions=[
                RemediationAction(
                    step=1,
                    tool=AllowedTool.ROLLBACK_DEPLOYMENT.value,
                    target_asset=target_asset,
                    parameters={"asset_id": target_asset, "target_version": "v2.4.0-stable"},
                )
            ],
            expected_result=f"Revert any recently deployed regression causing timeouts on {target_asset}",
            estimated_recovery_seconds=90,
            risk_estimate="LOW",
            downtime_estimate="Zero downtime (rolling canary rollback)",
            blast_radius=blast_radius or "Full service deployment rollback",
            confidence=88,
            rollback_method=f"Re-apply release artifact from container registry if rollback target exhibits migration faults.",
        )

        # Plan 4: Restore Configuration (Revert Config Drift)
        plan_restore_config = RemediationPlan(
            plan_id=f"PLAN-{short_id}-RESTORE-CONFIG",
            name=f"Restore Configuration Snapshot on {target_asset}",
            strategy="restore_configuration",
            actions=[
                RemediationAction(
                    step=1,
                    tool=AllowedTool.RESTORE_CONFIGURATION.value,
                    target_asset=target_asset,
                    parameters={"asset_id": target_asset, "config_snapshot_id": "cfg-stable-latest"},
                )
            ],
            expected_result=f"Restore verified stable configuration parameters for {target_asset}",
            estimated_recovery_seconds=20,
            risk_estimate="LOW",
            downtime_estimate="Zero downtime (dynamic configuration reload)",
            blast_radius=blast_radius or "Configuration state reload",
            confidence=90,
            rollback_method=f"Restore previous active configuration file if syntax validation fails on reload.",
        )

        # Plan 5: Clear Cache / Temporary Buffer
        plan_clear_cache = RemediationPlan(
            plan_id=f"PLAN-{short_id}-CLEAR-CACHE",
            name=f"Purge Temporary Cache and Buffers on {target_asset}",
            strategy="clear_cache",
            actions=[
                RemediationAction(
                    step=1,
                    tool=AllowedTool.CLEAR_CACHE.value,
                    target_asset=target_asset,
                    parameters={"asset_id": target_asset, "cache_pattern": "*"},
                )
            ],
            expected_result=f"Reclaim saturated memory/disk space on {target_asset}",
            estimated_recovery_seconds=15,
            risk_estimate="LOW",
            downtime_estimate="Zero downtime",
            blast_radius=blast_radius or "Local cache eviction",
            confidence=89,
            rollback_method=f"Restore and warm cache from persistent snapshot if cache miss rate causes query latency spike.",
        )

        return [plan_scale, plan_restart, plan_rollback, plan_clear_cache]

    @classmethod
    def validate_and_filter_plans(
        cls,
        raw_plans: List[Dict[str, Any]],
        target_asset: str,
        blast_radius: Any,
        correlation_id: str,
    ) -> List[RemediationPlan]:
        """
        Validate candidate plans from Gemini.
        Rejects plans with unknown tools, missing rollback, or duplicate strategies.
        Guarantees 2-4 distinct, fully validated plans.
        """
        validated_plans: List[RemediationPlan] = []
        seen_strategies: set = set()

        for raw in raw_plans:
            try:
                plan = RemediationPlan.model_validate(raw)

                # Ensure all actions strictly use whitelisted tools
                all_tools_valid = all(act.tool in ALLOWED_TOOL_NAMES for act in plan.actions)
                if not all_tools_valid:
                    logger.warning(f"Rejecting plan '{plan.name}': contains disallowed tools.")
                    continue

                # Ensure non-empty rollback method
                if not plan.rollback_method or len(plan.rollback_method.strip()) < 5:
                    logger.warning(f"Rejecting plan '{plan.name}': missing rollback method.")
                    continue

                # Enforce strategy diversity (no duplicate strategies)
                strat_key = plan.strategy.lower().strip()
                if strat_key in seen_strategies:
                    logger.warning(f"Rejecting duplicate plan strategy: '{strat_key}'")
                    continue

                seen_strategies.add(strat_key)
                validated_plans.append(plan)

                if len(validated_plans) >= 4:
                    break

            except (ValidationError, Exception) as e:
                logger.warning(f"Rejecting malformed plan: {e}")
                continue

        # If LLM produced fewer than 2 valid distinct plans, supplement from verified fallbacks
        if len(validated_plans) < 2:
            fallbacks = cls.generate_deterministic_plans(
                target_asset=target_asset,
                blast_radius=blast_radius,
                correlation_id=correlation_id,
            )
            for fb in fallbacks:
                if fb.strategy not in seen_strategies:
                    validated_plans.append(fb)
                    seen_strategies.add(fb.strategy)
                if len(validated_plans) >= 4:
                    break

        return validated_plans
