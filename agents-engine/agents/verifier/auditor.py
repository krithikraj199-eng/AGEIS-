"""
Deterministic Metric Auditor for AEGIS Ω Verifier Agent.
Performs pure Python before/after comparison on the exact triggering metric.
Zero LLM logic.
"""

from typing import Dict, Optional, Tuple
from .models import VerificationStatus


class DeterministicMetricAuditor:
    """
    Pure Python deterministic metric auditor for health verification.
    """

    # Standard healthy operational thresholds (upper boundaries for lower-is-better metrics)
    DEFAULT_THRESHOLDS: Dict[str, float] = {
        "cpu_percent": 80.0,
        "memory_percent": 85.0,
        "latency_ms": 200.0,
        "error_rate": 0.05,
        "packet_loss": 0.01,
        "db_connection_pool_saturation": 0.70,
    }

    # Metrics where higher value is better
    HIGHER_IS_BETTER: set = {
        "throughput_rps",
        "availability_pct",
        "healthy_replica_count",
    }

    @classmethod
    def get_threshold(cls, metric_name: str, before_val: float) -> float:
        """Get standard healthy threshold or derive one from before value."""
        norm_name = metric_name.lower().strip()
        if norm_name in cls.DEFAULT_THRESHOLDS:
            return cls.DEFAULT_THRESHOLDS[norm_name]
        return round(before_val * 0.5, 2)

    @classmethod
    def verify_metric(
        cls,
        metric_name: str,
        before_val: float,
        after_val: float,
        target_threshold: Optional[float] = None,
    ) -> Tuple[VerificationStatus, str, str]:
        """
        Deterministically compare before and after values of the EXACT SAME metric.
        Returns (status, expected_result, evidence).
        """
        norm_name = metric_name.lower().strip()
        threshold = target_threshold if target_threshold is not None else cls.get_threshold(norm_name, before_val)

        is_higher_better = norm_name in cls.HIGHER_IS_BETTER

        if is_higher_better:
            expected_result = f"{metric_name} >= {threshold}"
            if after_val < before_val:
                status = VerificationStatus.FAILED
                evidence = (
                    f"Metric '{metric_name}' worsened after remediation: dropped from {before_val} to {after_val}. "
                    f"Target threshold {expected_result} was not achieved."
                )
            elif after_val < threshold:
                status = VerificationStatus.FAILED
                evidence = (
                    f"Metric '{metric_name}' remained suboptimal at {after_val} (before: {before_val}). "
                    f"Target threshold {expected_result} was not met."
                )
            else:
                status = VerificationStatus.SUCCESS
                evidence = (
                    f"Metric '{metric_name}' recovered from {before_val} to {after_val}, meeting SLA {expected_result}."
                )
        else:
            # Lower is better (latency, cpu, memory, error rate)
            expected_result = f"{metric_name} <= {threshold}"

            # Case 1: Metric worsened
            if after_val > before_val:
                status = VerificationStatus.FAILED
                pct_increase = round(((after_val - before_val) / max(0.001, before_val)) * 100.0, 2)
                evidence = (
                    f"Metric '{metric_name}' worsened post-remediation: increased from {before_val} to {after_val} "
                    f"(+{pct_increase}%). Target SLA {expected_result} was violated."
                )
            # Case 2: Metric remained bad (still above threshold or no significant improvement)
            elif after_val > threshold:
                status = VerificationStatus.FAILED
                pct_drop = round(((before_val - after_val) / max(0.001, before_val)) * 100.0, 2)
                evidence = (
                    f"Metric '{metric_name}' remained elevated at {after_val} despite dropping {pct_drop}% from {before_val}. "
                    f"Failed to achieve target SLA {expected_result}."
                )
            # Case 3: Metric improved and is within healthy threshold
            else:
                status = VerificationStatus.SUCCESS
                pct_drop = round(((before_val - after_val) / max(0.001, before_val)) * 100.0, 2)
                evidence = (
                    f"Metric '{metric_name}' successfully recovered: dropped from {before_val} to {after_val} "
                    f"(-{pct_drop}%), returning within target SLA {expected_result}."
                )

        return status, expected_result, evidence
