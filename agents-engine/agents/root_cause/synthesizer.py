"""
Deterministic Root Cause Synthesizer and Discrepancy Detector for AEGIS Ω.
Combines Evidence, Dependency, and Security inputs with 100% traceability and zero fact invention.
"""

from typing import Any, Dict, List, Optional, Protocol, Tuple
from agents.dependency.models import BlastRadius
from agents.security.models import IncidentClassification
from .models import RootCauseOutput


class GeminiRootCauseSummarizerProtocol(Protocol):
    """Clean interface for optional Gemini phrasing of pre-synthesized root cause findings."""

    async def summarize_root_cause(
        self,
        root_cause: str,
        supporting_evidence: List[str],
        affected_systems: List[str],
        classification: str,
    ) -> str:
        """Phrases human-readable explanation from existing structured data only."""
        ...


class DeterministicRootCauseSynthesizer:
    """
    Synthesizes inputs from Evidence, Dependency, and Security agents.
    Strictly forbids inventing facts and guarantees full traceability.
    """

    @classmethod
    def check_discrepancy(
        cls,
        security_classification: str,
        security_risk_flag: bool,
        evidence_claims: List[str],
        evidence_metrics: List[str],
        detected_security_patterns: List[str],
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect discrepancies between Security and Evidence findings without silent suppression.
        """
        sec_class = str(security_classification).upper()
        has_actual_exploit_patterns = len(detected_security_patterns) > 0

        # Case 1: Security flags SECURITY_EVENT, but Evidence only shows operational resource exhaustion without exploit signatures
        if sec_class == IncidentClassification.SECURITY_EVENT.value or security_risk_flag:
            is_purely_operational = all(
                m in [
                    "query_latency_ms", "connection_pool_usage_pct", "cpu_utilization_pct",
                    "memory_used_pct", "disk_used_pct", "http_5xx_rate_pct", "active_connections", "deadlocks"
                ]
                for m in evidence_metrics
            )
            if is_purely_operational and evidence_metrics and not has_actual_exploit_patterns:
                return (
                    True,
                    "Discrepancy detected: Security classified incident as SECURITY_EVENT, but Evidence metrics "
                    "reflect operational resource exhaustion without exploit signatures. Preserving dual perspective for governance review.",
                )

        # Case 2: Security flags OPERATIONAL_FAILURE, but evidence claims or metrics indicate exploit/brute force
        if sec_class == IncidentClassification.OPERATIONAL_FAILURE.value and not security_risk_flag:
            has_exploit_metric = any(
                m in ["failed_ssh_attempts_1m", "cve_identifier", "unauthorized_admin_escalation"]
                for m in evidence_metrics
            )
            if has_exploit_metric or has_actual_exploit_patterns:
                return (
                    True,
                    "Discrepancy detected: Security classified incident as OPERATIONAL_FAILURE, but Evidence contains "
                    "unauthorized access or exploit metrics.",
                )

        return False, None

    @classmethod
    def build_causal_chain(
        cls,
        root_asset: str,
        downstream_services: List[str],
        primary_cause: str,
    ) -> List[str]:
        """
        Construct causal step-by-step chain traced along dependency graph.
        """
        chain = [f"Root Trigger: {root_asset} experienced {primary_cause}"]
        for idx, svc in enumerate(downstream_services, start=1):
            chain.append(f"Step {idx}: Failure cascaded downstream to {svc}")
        return chain
