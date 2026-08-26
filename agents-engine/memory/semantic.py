"""
Semantic Memory for AEGIS Ω Memory Bank.
Analyzes previous episodic incidents and extracts high-level generalized knowledge patterns using Gemini.
Example: "Database overload incidents frequently follow deployment events."
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Protocol
from pydantic import BaseModel, Field

from runtime.llm import get_gemini_client, GeminiClientWrapper
from .episodic import EpisodeRecord
from .storage import SemanticStoreProtocol, InMemoryStorageBackend

logger = logging.getLogger(__name__)


class SemanticPattern(BaseModel):
    """
    Schema for generalized semantic knowledge pattern:
    { pattern_id, pattern_statement, incident_types, confidence, supporting_incident_ids, extracted_at }
    """
    pattern_id: str
    pattern_statement: str = Field(
        description="Generalized insight or invariant statement (e.g. 'Database overload frequently follows deployment events')",
    )
    incident_types: List[str] = Field(
        default_factory=list,
        description="Associated incident categories or failure signatures",
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence score in the extracted pattern (0.0 to 1.0)",
    )
    supporting_incident_ids: List[str] = Field(
        default_factory=list,
        description="Historical incident IDs supporting this pattern",
    )
    extracted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class SemanticExtractorProtocol(Protocol):
    """Protocol for extracting semantic patterns from historical episodes."""

    async def extract_patterns(self, episodes: List[EpisodeRecord]) -> List[SemanticPattern]:
        ...


class GeminiSemanticPatternExtractor:
    """
    Uses Gemini LLM exclusively for generalized pattern synthesis across episodic memory.
    """

    def __init__(self, client_wrapper: Optional[GeminiClientWrapper] = None):
        self.client_wrapper = client_wrapper or get_gemini_client()

    async def extract_patterns(self, episodes: List[EpisodeRecord]) -> List[SemanticPattern]:
        """Call Gemini to discover cross-incident invariants and failure correlations."""
        if not episodes:
            return []

        # Prepare summary of episodes for prompt context
        episodes_summary = [
            {
                "incident_id": ep.incident_id,
                "root_cause": ep.root_cause,
                "signature": ep.incident_signature,
                "strategy": ep.plan.get("strategy", "unknown"),
                "outcome": ep.outcome,
            }
            for ep in episodes[-20:]  # Last 20 episodes
        ]

        if not self.client_wrapper.is_configured:
            # Fallback deterministic pattern synthesizer when API key is missing
            return self._heuristic_fallback_extraction(episodes)

        prompt = (
            "Analyze the following operational incident episodes and extract 1-3 generalized "
            "semantic patterns regarding common failure modes, cascading correlations, or remediation effectiveness.\n"
            f"EPISODES DATA:\n{json.dumps(episodes_summary, indent=2)}\n\n"
            "Output strictly valid JSON with schema:\n"
            "[\n"
            "  {\n"
            "    \"pattern_statement\": \"General invariant description\",\n"
            "    \"incident_types\": [\"DATABASE_TIMEOUT\", \"RESOURCE_EXHAUSTION\"],\n"
            "    \"confidence\": 0.90,\n"
            "    \"supporting_incident_ids\": [\"INC-01\", \"INC-02\"]\n"
            "  }\n"
            "]"
        )

        try:
            client = self.client_wrapper.get_client()
            response = await client.aio.models.generate_content(
                model=self.client_wrapper.model_name,
                contents=prompt,
            )
            raw_text = response.text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(raw_text)
            patterns = []
            now_ts = datetime.now(timezone.utc).isoformat()
            for idx, item in enumerate(parsed):
                patterns.append(
                    SemanticPattern(
                        pattern_id=f"PAT-{int(datetime.now().timestamp())}-{idx + 1}",
                        pattern_statement=item.get("pattern_statement", ""),
                        incident_types=item.get("incident_types", []),
                        confidence=float(item.get("confidence", 0.85)),
                        supporting_incident_ids=item.get("supporting_incident_ids", [ep.incident_id for ep in episodes]),
                        extracted_at=now_ts,
                    )
                )
            return patterns
        except Exception as e:
            logger.warning(f"Gemini pattern extraction failed: {e}. Using deterministic fallback.")
            return self._heuristic_fallback_extraction(episodes)

    def _heuristic_fallback_extraction(self, episodes: List[EpisodeRecord]) -> List[SemanticPattern]:
        """Deterministic pattern synthesizer for offline / test operation."""
        patterns = []
        now_ts = datetime.now(timezone.utc).isoformat()
        db_episodes = [ep for ep in episodes if "DATABASE" in ep.root_cause.upper() or "DATABASE" in ep.incident_signature.upper()]
        if len(db_episodes) >= 1:
            patterns.append(
                SemanticPattern(
                    pattern_id=f"PAT-HEURISTIC-DB-{len(db_episodes)}",
                    pattern_statement="Database overload incidents frequently correlate with connection pool saturation and require replica scaling.",
                    incident_types=["DATABASE_TIMEOUT", "CONNECTION_POOL_EXHAUSTION"],
                    confidence=0.92,
                    supporting_incident_ids=[ep.incident_id for ep in db_episodes],
                    extracted_at=now_ts,
                )
            )
        return patterns


class SemanticMemory:
    """
    Semantic Memory Engine: Stores and queries generalized operational knowledge.
    """

    def __init__(
        self,
        store: Optional[SemanticStoreProtocol] = None,
        extractor: Optional[SemanticExtractorProtocol] = None,
    ):
        self.store = store or InMemoryStorageBackend()
        self.extractor = extractor or GeminiSemanticPatternExtractor()

    async def analyze_and_extract_patterns(self, episodes: List[EpisodeRecord]) -> List[SemanticPattern]:
        """Extract new patterns from episodic memory and store them."""
        patterns = await self.extractor.extract_patterns(episodes)
        for pat in patterns:
            self.store.save_pattern(pat.model_dump())
            logger.info(f"Stored semantic pattern '{pat.pattern_id}': {pat.pattern_statement}")
        return patterns

    def store_pattern(self, pattern: SemanticPattern) -> str:
        """Manually store a semantic pattern."""
        self.store.save_pattern(pattern.model_dump())
        return pattern.pattern_id

    def search_patterns(self, query: str, limit: int = 5) -> List[SemanticPattern]:
        """Search generalized patterns by text query."""
        raw_list = self.store.search_patterns(query=query, limit=limit)
        return [SemanticPattern.model_validate(r) for r in raw_list]

    def list_patterns(self) -> List[SemanticPattern]:
        """List all stored semantic patterns."""
        raw_list = self.store.list_all_patterns()
        return [SemanticPattern.model_validate(r) for r in raw_list]
