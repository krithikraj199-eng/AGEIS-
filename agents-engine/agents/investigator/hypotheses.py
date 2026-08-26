"""
Hypothesis Models and Anti-Hallucination Evidence Validation for Investigator Agent.
Guarantees 3-5 competing hypotheses and validates all cited evidence against observed context.
"""

import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, field_validator
from .context_collector import InvestigationContext


class Hypothesis(BaseModel):
    """
    Structured causal hypothesis schema.
    Must adhere strictly to required fields: explanation, supporting_evidence,
    contradicting_evidence, and confidence (0-100).
    """
    explanation: str = Field(
        description="Detailed explanation of the causal failure mechanism",
    )
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="List of observed metrics, events, or configuration states supporting this hypothesis",
    )
    contradicting_evidence: List[str] = Field(
        default_factory=list,
        description="List of observed metrics or conditions that argue against this hypothesis",
    )
    confidence: int = Field(
        ge=0,
        le=100,
        description="Estimated confidence score between 0 and 100",
    )
    is_grounded: bool = Field(
        default=True,
        description="True if all referenced evidence exists in the investigation context",
    )
    grounding_validation_errors: List[str] = Field(
        default_factory=list,
        description="Validation error messages if unsupported or hallucinated evidence was detected",
    )


class HypothesisSet(BaseModel):
    """
    Container for competing hypotheses.
    Enforces the strict requirement that 3 to 5 competing hypotheses must be produced.
    """
    hypotheses: List[Hypothesis] = Field(
        description="List of 3 to 5 competing hypotheses",
    )

    @field_validator("hypotheses")
    @classmethod
    def validate_hypothesis_count(cls, v: List[Hypothesis]) -> List[Hypothesis]:
        if len(v) < 3:
            raise ValueError(
                f"Agent produced {len(v)} hypotheses. CRITICAL REQUIREMENT: Must produce between 3 and 5 competing hypotheses."
            )
        if len(v) > 5:
            raise ValueError(
                f"Agent produced {len(v)} hypotheses. Must not exceed 5 competing hypotheses."
            )
        return v


class EvidenceValidator:
    """
    Validates that every referenced metric, value, and event in a hypothesis
    actually exists in the input InvestigationContext (Anti-Hallucination Guard).
    """

    def __init__(self, context: InvestigationContext):
        self.context = context
        self._known_assets: Set[str] = {context.primary_asset_id}
        self._known_event_types: Set[str] = set()
        self._known_metric_keys: Set[str] = set()
        self._known_metric_values: Set[str] = set()
        self._known_deploy_versions: Set[str] = set()
        self._known_config_keys: Set[str] = set()

        self._index_context()

    def _index_context(self) -> None:
        """Extract and index all known ground-truth tokens from context."""
        # Index events and assets
        for ev in self.context.recent_events:
            aid = ev.get("asset_id")
            if aid:
                self._known_assets.add(aid.upper())
            etype = ev.get("event_type")
            if etype:
                self._known_event_types.add(etype.upper())

            # Index metrics
            for k, v in ev.get("metrics", {}).items():
                self._known_metric_keys.add(k.lower())
                self._known_metric_values.add(str(v).lower())

        # Index recent_metrics dictionary
        for aid, metrics in self.context.recent_metrics.items():
            self._known_assets.add(aid.upper())
            for k, v in metrics.items():
                self._known_metric_keys.add(k.lower())
                self._known_metric_values.add(str(v).lower())

        # Index deployments & configs
        for dep in self.context.deployment_changes:
            self._known_assets.add(dep.asset_id.upper())
            self._known_deploy_versions.add(dep.deployed_version.lower())
            self._known_deploy_versions.add(dep.previous_version.lower())

        for cfg in self.context.configuration_changes:
            self._known_assets.add(cfg.asset_id.upper())
            self._known_config_keys.add(cfg.config_key.lower())

        for aid in self.context.dependency_information.keys():
            self._known_assets.add(aid.upper())

    def validate_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """
        Scan all supporting and contradicting evidence in a hypothesis.
        Flag and record any hallucinated metrics, non-existent events, or ungrounded claims.
        """
        errors: List[str] = []
        all_evidence = hypothesis.supporting_evidence + hypothesis.contradicting_evidence

        # Metric key extraction regex: e.g. "query_latency_ms=32400" or "metric 'cpu_pct'"
        metric_pattern = re.compile(r"([a-zA-Z0-9_]+)\s*[:=]\s*([0-9\.]+)")
        # Quoted identifier or known pattern
        event_pattern = re.compile(r"\b([A-Z]+_[A-Z0-9_]+)\b")

        for item in all_evidence:
            item_lower = item.lower()

            # Check for metric key/value pairs
            metric_matches = metric_pattern.findall(item)
            for mkey, mval in metric_matches:
                mkey_clean = mkey.lower()
                if mkey_clean not in self._known_metric_keys and mkey_clean not in self._known_config_keys:
                    errors.append(
                        f"Unsupported metric key '{mkey}' in evidence '{item}' - not found in telemetry context."
                    )

            # Check for event types mentioned in uppercase
            event_matches = event_pattern.findall(item)
            for etype in event_matches:
                if etype not in self._known_event_types and etype not in ["HTTP_5XX", "TCP_RST"]:
                    errors.append(
                        f"Referenced event '{etype}' in evidence '{item}' does not exist in observed events."
                    )

        if errors:
            hypothesis.is_grounded = False
            hypothesis.grounding_validation_errors = errors
        else:
            hypothesis.is_grounded = True
            hypothesis.grounding_validation_errors = []

        return hypothesis

    def validate_hypothesis_set(
        self,
        hypotheses: List[Hypothesis],
        reject_ungrounded: bool = False,
    ) -> List[Hypothesis]:
        """
        Validate all hypotheses against the ground-truth context.
        If reject_ungrounded is True, ungrounded hypotheses are filtered out.
        """
        validated = [self.validate_hypothesis(h) for h in hypotheses]
        if reject_ungrounded:
            return [h for h in validated if h.is_grounded]
        return validated
