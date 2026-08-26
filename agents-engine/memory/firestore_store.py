"""
Google Cloud Firestore Memory Store for AEGIS Ω Intelligence Engine.
Stores persistent memory artifacts in Firestore collections:
- episodic_memory
- semantic_patterns
- procedural_stats
- session_state
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from memory.storage import (
    EpisodicStoreProtocol,
    InMemoryStorageBackend,
    ProceduralStoreProtocol,
    SemanticStoreProtocol,
)
from runtime.config import get_settings

logger = logging.getLogger(__name__)


class FirestoreStorageBackend(EpisodicStoreProtocol, SemanticStoreProtocol, ProceduralStoreProtocol):
    """
    Firestore Storage Backend for AEGIS Ω Tripartite Memory Bank.
    Connects to live Google Cloud Firestore when configured, with fallback to in-memory store.
    """

    COLLECTION_EPISODIC = "episodic_memory"
    COLLECTION_SEMANTIC = "semantic_patterns"
    COLLECTION_PROCEDURAL = "procedural_stats"
    COLLECTION_SESSION = "session_state"

    def __init__(
        self,
        project_id: Optional[str] = None,
        database_id: Optional[str] = None,
        enable_firestore: Optional[bool] = None,
    ):
        settings = get_settings()
        self.project_id = project_id or settings.gcp_project_id
        self.database_id = database_id or settings.firestore_database_id
        self.enable_firestore = (
            enable_firestore if enable_firestore is not None else settings.enable_firestore
        )
        self._fallback = InMemoryStorageBackend()
        self._firestore_client = None

        if self.enable_firestore:
            self._init_firestore_client()

    def _init_firestore_client(self) -> None:
        """Initialize Google Cloud Firestore client."""
        try:
            from google.cloud import firestore
            self._firestore_client = firestore.Client(
                project=self.project_id,
                database=self.database_id,
            )
            logger.info(f"Connected to Google Cloud Firestore (database: {self.database_id})")
        except Exception as e:
            logger.warning(
                f"Could not initialize Firestore client ({e}). Operating in resilient fallback mode."
            )
            self._firestore_client = None

    # -------------------------------------------------------------------------
    # Episodic Store Protocol
    # -------------------------------------------------------------------------
    def save_episode(self, episode_data: Dict[str, Any]) -> str:
        """Save episode to Firestore and fallback cache."""
        inc_id = self._fallback.save_episode(episode_data)
        if self._firestore_client:
            try:
                doc_ref = self._firestore_client.collection(self.COLLECTION_EPISODIC).document(inc_id)
                doc_ref.set(episode_data)
            except Exception as e:
                logger.error(f"Firestore error saving episode {inc_id}: {e}")
        return inc_id

    def get_episode(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve episode from Firestore or fallback cache."""
        if self._firestore_client:
            try:
                doc = self._firestore_client.collection(self.COLLECTION_EPISODIC).document(incident_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                logger.error(f"Firestore error reading episode {incident_id}: {e}")
        return self._fallback.get_episode(incident_id)

    def query_episodes(
        self,
        query: str = "",
        signature: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Query episodes matching signature or text."""
        return self._fallback.query_episodes(query, signature, limit)

    def list_all_episodes(self) -> List[Dict[str, Any]]:
        """List all episodes."""
        return self._fallback.list_all_episodes()

    # -------------------------------------------------------------------------
    # Semantic Store Protocol
    # -------------------------------------------------------------------------
    def save_pattern(self, pattern_data: Dict[str, Any]) -> str:
        """Save semantic failure pattern to Firestore and fallback cache."""
        pat_id = self._fallback.save_pattern(pattern_data)
        if self._firestore_client:
            try:
                doc_ref = self._firestore_client.collection(self.COLLECTION_SEMANTIC).document(pat_id)
                doc_ref.set(pattern_data)
            except Exception as e:
                logger.error(f"Firestore error saving semantic pattern {pat_id}: {e}")
        return pat_id

    def search_patterns(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search semantic patterns."""
        return self._fallback.search_patterns(query, limit)

    def list_all_patterns(self) -> List[Dict[str, Any]]:
        """List all semantic patterns."""
        return self._fallback.list_all_patterns()

    # -------------------------------------------------------------------------
    # Procedural Store Protocol
    # -------------------------------------------------------------------------
    def record_outcome(
        self,
        signature: str,
        strategy: str,
        success: bool,
    ) -> Dict[str, Any]:
        """Record empirical strategy execution outcome."""
        res = self._fallback.record_outcome(signature, strategy, success)
        if self._firestore_client:
            try:
                doc_id = f"{signature}:{strategy}".replace("/", "_")
                doc_ref = self._firestore_client.collection(self.COLLECTION_PROCEDURAL).document(doc_id)
                doc_ref.set(res)
            except Exception as e:
                logger.error(f"Firestore error recording procedural stat: {e}")
        return res

    def get_strategy_stats(self, signature: str) -> Dict[str, Dict[str, Any]]:
        """Get strategy statistics for an incident signature."""
        return self._fallback.get_strategy_stats(signature)

    def get_all_stats(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Get all empirical strategy statistics."""
        return self._fallback.get_all_stats()

    def clear(self) -> None:
        """Clear local fallback memory cache."""
        self._fallback.clear()


# Global singleton instance
_global_firestore_backend: Optional[FirestoreStorageBackend] = None


def get_firestore_backend() -> FirestoreStorageBackend:
    """Retrieve or initialize the global FirestoreStorageBackend singleton."""
    global _global_firestore_backend
    if _global_firestore_backend is None:
        _global_firestore_backend = FirestoreStorageBackend()
    return _global_firestore_backend
