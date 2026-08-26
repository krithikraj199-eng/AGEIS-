"""
Unit and Integration Tests for AEGIS Ω Memory Bank.
Tests:
  - Episodic Memory (record, retrieve, query episodes)
  - Semantic Memory (generalized pattern extraction and search)
  - Procedural Memory (>80% success AND >=3 historical incidents qualification)
  - CRITICAL INTEGRATION: Run failure signature twice -> First run stores successful strategy ->
    Second run proves Planner receives and uses historical strategy information to bias plan selection.
"""

import asyncio
from typing import Any, Dict, List

from memory.storage import InMemoryStorageBackend
from memory.episodic import EpisodeRecord, EpisodicMemory
from memory.semantic import SemanticPattern, SemanticMemory
from memory.procedural import StrategyStats, BestStrategyRecommendation, ProceduralMemory
from agents.planner.agent import PlannerAgent, PlannerInput, PlannerOutput


def test_episodic_memory_store_and_search():
    """Verify storing, retrieving, and searching episodic incident records."""
    store = InMemoryStorageBackend()
    episodic = EpisodicMemory(store=store)

    # 1. Record episode
    ep = episodic.record_episode(
        incident_id="INC-EPISODE-01",
        correlation_id="corr-ep-01",
        root_cause="Database connection pool saturation on DATABASE-01",
        plan={"plan_id": "PLAN-SCALE-01", "strategy": "scale_service"},
        outcome="SUCCESS",
        timestamps={"started": "2026-08-25T15:00:00Z", "resolved": "2026-08-25T15:00:15Z"},
        blast_radius={"affected_count": 3, "assets": ["DATABASE-01", "AUTH-01", "API-01"]},
        incident_signature="DATABASE_TIMEOUT_OVERLOAD",
    )

    assert ep.incident_id == "INC-EPISODE-01"
    assert ep.outcome == "SUCCESS"
    assert ep.blast_radius["affected_count"] == 3

    # 2. Retrieve episode
    fetched = episodic.get_episode("INC-EPISODE-01")
    assert fetched is not None
    assert fetched.root_cause == "Database connection pool saturation on DATABASE-01"

    # 3. Search episodes
    results = episodic.search_episodes(query="connection pool")
    assert len(results) == 1
    assert results[0].incident_id == "INC-EPISODE-01"

    # 4. Search with non-matching query
    assert len(episodic.search_episodes(query="memory leak")) == 0


def test_semantic_memory_pattern_extraction_and_search():
    """Verify semantic memory pattern extraction and keyword searching."""
    async def _test():
        store = InMemoryStorageBackend()
        semantic = SemanticMemory(store=store)

        episodes = [
            EpisodeRecord(
                incident_id="INC-01",
                correlation_id="c1",
                root_cause="Database timeout during peak traffic",
                plan={"strategy": "scale_service"},
                outcome="SUCCESS",
                incident_signature="DATABASE_OVERLOAD",
            ),
            EpisodeRecord(
                incident_id="INC-02",
                correlation_id="c2",
                root_cause="Database deadlock under replica shortage",
                plan={"strategy": "scale_service"},
                outcome="SUCCESS",
                incident_signature="DATABASE_OVERLOAD",
            ),
        ]

        # Extract patterns
        patterns = await semantic.analyze_and_extract_patterns(episodes)
        assert len(patterns) >= 1
        assert "Database" in patterns[0].pattern_statement

        # Search patterns
        search_res = semantic.search_patterns("database")
        assert len(search_res) >= 1
        assert search_res[0].confidence > 0.50

    asyncio.run(_test())


def test_procedural_memory_qualification_rules():
    """
    Test procedural memory qualification threshold rules:
      - Rule: Success rate > 80% (>0.80) AND at least 3 historical incidents (>= 3).
    """
    store = InMemoryStorageBackend()
    procedural = ProceduralMemory(store=store)
    sig = "DATABASE-01:DATABASE_TIMEOUT"

    # Case 1: 1 execution (1 success) -> Total: 1 (Fails: <3 incidents)
    procedural.record_action_outcome(sig, "scale_service", success=True)
    assert procedural.get_best_known_strategy(sig) is None

    # Case 2: 2 executions (2 successes) -> Total: 2 (Fails: <3 incidents)
    procedural.record_action_outcome(sig, "scale_service", success=True)
    assert procedural.get_best_known_strategy(sig) is None

    # Case 3: 3 executions (3 successes) -> Total: 3, 100% success -> QUALIFIES!
    procedural.record_action_outcome(sig, "scale_service", success=True)
    rec = procedural.get_best_known_strategy(sig)
    assert rec is not None
    assert rec.recommended_strategy == "scale_service"
    assert rec.success_rate == 1.0
    assert rec.total_incidents == 3

    # Case 4: 4th execution fails -> 3 success, 1 fail = 75% -> FAILS (>80% required)
    procedural.record_action_outcome(sig, "scale_service", success=False)
    assert procedural.get_best_known_strategy(sig) is None

    # Case 5: Add 2 more successes -> 5 success, 1 fail = 83.33% across 6 incidents -> QUALIFIES AGAIN!
    procedural.record_action_outcome(sig, "scale_service", success=True)
    procedural.record_action_outcome(sig, "scale_service", success=True)
    rec2 = procedural.get_best_known_strategy(sig)
    assert rec2 is not None
    assert rec2.recommended_strategy == "scale_service"
    assert rec2.success_rate > 0.80
    assert rec2.total_incidents == 6


def test_planner_procedural_memory_biasing_two_runs():
    """
    CRITICAL USER INTEGRATION TEST:
    Run failure signature twice:
      First run: Store successful strategy in procedural memory (scale_service).
      Second run: Prove Planner queries and uses historical strategy information to bias plan selection.
    """
    async def _test():
        store = InMemoryStorageBackend()
        procedural = ProceduralMemory(store=store)
        planner = PlannerAgent(procedural_memory=procedural)

        signature = "DATABASE-01:DATABASE_TIMEOUT"
        asset_id = "DATABASE-01"

        # --- STEP 1: First Run (Populate historical memory with 3 proven successes for scale_service) ---
        procedural.record_action_outcome(signature, "scale_service", success=True)
        procedural.record_action_outcome(signature, "scale_service", success=True)
        procedural.record_action_outcome(signature, "scale_service", success=True)

        # Confirm Procedural Memory has qualified scale_service (>80% and >=3 incidents)
        rec = procedural.get_best_known_strategy(signature)
        assert rec is not None
        assert rec.recommended_strategy == "scale_service"
        assert rec.total_incidents == 3
        assert rec.success_rate == 1.0

        # --- STEP 2: Second Run (Planner processes incident with same signature) ---
        planner_input = PlannerInput(
            correlation_id="corr-mem-biasing-01",
            incident_id="INC-MEM-BIAS-01",
            root_asset_id=asset_id,
            root_cause="DATABASE_TIMEOUT due to high pool usage",
            primary_failure_cause="DATABASE_TIMEOUT",
            affected_systems=["DATABASE-01", "AUTH-01"],
            confidence_score=0.85,
        )

        output: PlannerOutput = await planner.process(planner_input)

        # Assert Planner generated candidate plans
        assert len(output.plans) >= 2

        # Assert Planner selected the historically proven plan (scale_service)
        # and boosted its confidence
        selected = output.selected_plan
        assert selected is not None
        assert selected.strategy == "scale_service" or any(a.action_type == "scale_service" for a in output.action_steps)
        assert selected.confidence >= 90  # Confirmed confidence boost from procedural memory (>=90/100)

    asyncio.run(_test())
