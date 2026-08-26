"""
Pluggable Storage Interfaces and Backend Implementations for AEGIS Ω Memory Bank.
Enables transparent replacement of local storage with Google Cloud Firestore / Cloud SQL.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class EpisodicStoreProtocol(Protocol):
    """Protocol for persisting and querying episodic incident records."""

    def save_episode(self, episode_data: Dict[str, Any]) -> str:
        ...

    def get_episode(self, incident_id: str) -> Optional[Dict[str, Any]]:
        ...

    def query_episodes(
        self,
        query: str = "",
        signature: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        ...

    def list_all_episodes(self) -> List[Dict[str, Any]]:
        ...


class SemanticStoreProtocol(Protocol):
    """Protocol for storing and searching semantic knowledge patterns."""

    def save_pattern(self, pattern_data: Dict[str, Any]) -> str:
        ...

    def search_patterns(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        ...

    def list_all_patterns(self) -> List[Dict[str, Any]]:
        ...


class ProceduralStoreProtocol(Protocol):
    """Protocol for storing empirical action statistics per incident signature."""

    def record_outcome(
        self,
        signature: str,
        strategy: str,
        success: bool,
    ) -> Dict[str, Any]:
        ...

    def get_strategy_stats(self, signature: str) -> Dict[str, Dict[str, Any]]:
        ...

    def get_all_stats(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        ...


class InMemoryStorageBackend:
    """
    Default in-memory storage implementation for AEGIS Ω Memory Bank.
    Implements EpisodicStoreProtocol, SemanticStoreProtocol, and ProceduralStoreProtocol.
    """

    def __init__(self):
        self._episodes: Dict[str, Dict[str, Any]] = {}
        self._patterns: Dict[str, Dict[str, Any]] = {}
        self._procedural: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # --- Episodic Methods ---
    def save_episode(self, episode_data: Dict[str, Any]) -> str:
        inc_id = episode_data.get("incident_id", f"INC-{len(self._episodes) + 1}")
        self._episodes[inc_id] = dict(episode_data)
        return inc_id

    def get_episode(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return self._episodes.get(incident_id)

    def query_episodes(
        self,
        query: str = "",
        signature: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        results = []
        q_lower = query.lower() if query else ""

        for ep in self._episodes.values():
            if signature and ep.get("incident_signature") != signature:
                continue
            if q_lower:
                rc = ep.get("root_cause", "").lower()
                outcome = ep.get("outcome", "").lower()
                sig = ep.get("incident_signature", "").lower()
                if q_lower not in rc and q_lower not in outcome and q_lower not in sig:
                    continue
            results.append(ep)
            if len(results) >= limit:
                break
        return results

    def list_all_episodes(self) -> List[Dict[str, Any]]:
        return list(self._episodes.values())

    # --- Semantic Methods ---
    def save_pattern(self, pattern_data: Dict[str, Any]) -> str:
        pat_id = pattern_data.get("pattern_id", f"PAT-{len(self._patterns) + 1}")
        self._patterns[pat_id] = dict(pattern_data)
        return pat_id

    def search_patterns(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        results = []
        q_lower = query.lower()
        for pat in self._patterns.values():
            stmt = pat.get("pattern_statement", "").lower()
            types = " ".join(pat.get("incident_types", [])).lower()
            if q_lower in stmt or q_lower in types:
                results.append(pat)
            if len(results) >= limit:
                break
        return results

    def list_all_patterns(self) -> List[Dict[str, Any]]:
        return list(self._patterns.values())

    # --- Procedural Methods ---
    def record_outcome(
        self,
        signature: str,
        strategy: str,
        success: bool,
    ) -> Dict[str, Any]:
        norm_sig = signature.strip().upper()
        norm_strat = strategy.strip().lower()

        if norm_sig not in self._procedural:
            self._procedural[norm_sig] = {}

        if norm_strat not in self._procedural[norm_sig]:
            self._procedural[norm_sig][norm_strat] = {
                "strategy": norm_strat,
                "success_count": 0,
                "failure_count": 0,
                "total_executions": 0,
                "success_rate": 0.0,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        rec = self._procedural[norm_sig][norm_strat]
        if success:
            rec["success_count"] += 1
        else:
            rec["failure_count"] += 1

        rec["total_executions"] = rec["success_count"] + rec["failure_count"]
        rec["success_rate"] = round(rec["success_count"] / max(1, rec["total_executions"]), 4)
        rec["last_updated"] = datetime.now(timezone.utc).isoformat()
        return rec

    def get_strategy_stats(self, signature: str) -> Dict[str, Dict[str, Any]]:
        norm_sig = signature.strip().upper()
        return dict(self._procedural.get(norm_sig, {}))

    def get_all_stats(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        return dict(self._procedural)

    def clear(self) -> None:
        """Clear all in-memory episodic, semantic, and procedural records."""
        self._episodes.clear()
        self._patterns.clear()
        self._procedural.clear()
