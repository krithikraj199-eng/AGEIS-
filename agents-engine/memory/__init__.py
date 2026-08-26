"""
Memory Bank Package for AEGIS Ω.
Provides Episodic, Semantic, and Procedural Memory systems.
"""

from .storage import (
    EpisodicStoreProtocol,
    SemanticStoreProtocol,
    ProceduralStoreProtocol,
    InMemoryStorageBackend,
)
from .episodic import EpisodeRecord, EpisodicMemory
from .semantic import (
    SemanticPattern,
    SemanticExtractorProtocol,
    GeminiSemanticPatternExtractor,
    SemanticMemory,
)
from .procedural import (
    StrategyStats,
    BestStrategyRecommendation,
    ProceduralMemory,
)

# Global shared singleton instances for the runtime
_global_storage = InMemoryStorageBackend()
episodic_memory = EpisodicMemory(store=_global_storage)
semantic_memory = SemanticMemory(store=_global_storage)
procedural_memory = ProceduralMemory(store=_global_storage)

__all__ = [
    "EpisodicStoreProtocol",
    "SemanticStoreProtocol",
    "ProceduralStoreProtocol",
    "InMemoryStorageBackend",
    "EpisodeRecord",
    "EpisodicMemory",
    "SemanticPattern",
    "SemanticExtractorProtocol",
    "GeminiSemanticPatternExtractor",
    "SemanticMemory",
    "StrategyStats",
    "BestStrategyRecommendation",
    "ProceduralMemory",
    "episodic_memory",
    "semantic_memory",
    "procedural_memory",
]
