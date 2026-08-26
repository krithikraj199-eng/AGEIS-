"""
Unit and Integration Tests for GCP Adapters:
- Google Cloud Pub/Sub Event Bus (5 standard topics)
- Cloud SQL PostgreSQL Storage Adapter
- Google Cloud Firestore Memory Adapter
"""

import asyncio
from datetime import datetime, timezone

from runtime.pubsub_bus import (
    GCPPubSubEventBus,
    GCP_TOPIC_INCIDENT_DETECTED,
    GCP_TOPIC_INCIDENT_INVESTIGATED,
    GCP_TOPIC_PLAN_SELECTED,
    GCP_TOPIC_ACTION_EXECUTED,
    GCP_TOPIC_INCIDENT_RESOLVED,
    REQUIRED_PUBSUB_TOPICS,
)
from storage.cloud_sql import CloudSQLStorage
from memory.firestore_store import FirestoreStorageBackend
from mocks.event_generator import SystemEvent, EventType, Severity


def test_pubsub_event_bus_five_required_topics_mapping():
    """Verify all 5 required GCP Pub/Sub topics are defined and mapped."""
    assert len(REQUIRED_PUBSUB_TOPICS) == 5
    assert GCP_TOPIC_INCIDENT_DETECTED in REQUIRED_PUBSUB_TOPICS
    assert GCP_TOPIC_INCIDENT_INVESTIGATED in REQUIRED_PUBSUB_TOPICS
    assert GCP_TOPIC_PLAN_SELECTED in REQUIRED_PUBSUB_TOPICS
    assert GCP_TOPIC_ACTION_EXECUTED in REQUIRED_PUBSUB_TOPICS
    assert GCP_TOPIC_INCIDENT_RESOLVED in REQUIRED_PUBSUB_TOPICS


def test_pubsub_event_bus_publishing_and_envelope():
    """Verify GCPPubSubEventBus captures and formats envelopes for Pub/Sub topics."""
    async def _test():
        bus = GCPPubSubEventBus(project_id="test-project", enable_gcp_pubsub=False)

        # 1. Publish raw telemetry -> incident.detected
        ev = SystemEvent(
            asset_id="DATABASE-01",
            event_type=EventType.DATABASE_TIMEOUT,
            severity=Severity.CRITICAL,
            metrics={"latency_ms": 850.0},
        )
        await bus.publish("telemetry.raw", ev)

        # 2. Publish root cause -> incident.investigated
        await bus.publish("incident.root_cause", {"incident_id": "INC-01", "root_cause": "pool_exhaustion"})

        # 3. Publish plan -> plan.selected
        await bus.publish("incident.plan_formulated", {"plan_id": "PLAN-01", "strategy": "scale"})

        # 4. Publish actuation -> action.executed
        await bus.publish("incident.actuated", {"action": "scale_service", "asset_id": "DATABASE-01"})

        # 5. Publish resolved -> incident.resolved
        await bus.publish("incident.resolved", {"incident_id": "INC-01", "status": "RESOLVED"})

        messages = bus.published_gcp_messages
        assert len(messages) == 5

        gcp_topics = [m["gcp_topic"] for m in messages]
        assert GCP_TOPIC_INCIDENT_DETECTED in gcp_topics
        assert GCP_TOPIC_INCIDENT_INVESTIGATED in gcp_topics
        assert GCP_TOPIC_PLAN_SELECTED in gcp_topics
        assert GCP_TOPIC_ACTION_EXECUTED in gcp_topics
        assert GCP_TOPIC_INCIDENT_RESOLVED in gcp_topics

    asyncio.run(_test())


def test_cloud_sql_storage_lifecycle():
    """Verify Cloud SQL storage saves and queries incidents, plans, and audit entries."""
    async def _test():
        sql = CloudSQLStorage(enable_cloud_sql=False)
        await sql.initialize()

        # Save incident
        inc_id = await sql.save_incident({
            "incident_id": "INC-SQL-001",
            "correlation_id": "corr-sql-001",
            "asset_id": "DATABASE-01",
            "event_type": "DATABASE_TIMEOUT",
            "severity": "CRITICAL",
            "status": "RESOLVED",
            "root_cause": "Connection pool exhaustion",
            "blast_radius": 0.85,
        })
        assert inc_id == "INC-SQL-001"

        retrieved_inc = await sql.get_incident("INC-SQL-001")
        assert retrieved_inc is not None
        assert retrieved_inc["asset_id"] == "DATABASE-01"
        assert retrieved_inc["status"] == "RESOLVED"

        # Save plan
        plan_id = await sql.save_plan({
            "plan_id": "PLAN-SQL-001",
            "incident_id": "INC-SQL-001",
            "strategy": "scale_service",
            "risk_estimate": "LOW",
            "risk_score": 25,
            "rollback_method": "scale down",
            "actions": [{"tool": "scale_service", "target_asset": "DATABASE-01"}],
        })
        assert plan_id == "PLAN-SQL-001"

        retrieved_plan = await sql.get_plan("PLAN-SQL-001")
        assert retrieved_plan is not None
        assert retrieved_plan["strategy"] == "scale_service"

        # Save audit record
        audit_id = await sql.save_audit_record({
            "plan_id": "PLAN-SQL-001",
            "tool_name": "scale_service",
            "params": {"factor": 2.0},
            "actor": "ExecutorAgent",
            "status": "SUCCESS",
        })
        assert audit_id is not None

        records = await sql.list_audit_records()
        assert len(records) >= 1
        assert records[0]["tool_name"] == "scale_service"

    asyncio.run(_test())


def test_firestore_memory_storage_protocols():
    """Verify Firestore storage backend implements Episodic, Semantic, and Procedural protocols."""
    fs = FirestoreStorageBackend(enable_firestore=False)

    # 1. Episodic Store Protocol
    ep_id = fs.save_episode({
        "incident_id": "INC-FS-001",
        "correlation_id": "corr-fs-001",
        "root_cause": "Auth JWT memory leak",
        "outcome": "SUCCESS",
        "signature": "AUTH-01:LOGIN_FAILURE",
    })
    assert ep_id == "INC-FS-001"
    ep = fs.get_episode("INC-FS-001")
    assert ep is not None
    assert ep["root_cause"] == "Auth JWT memory leak"

    # 2. Semantic Store Protocol
    pat_id = fs.save_pattern({
        "pattern_statement": "Database latency cascades into auth login timeouts",
        "confidence_score": 0.92,
        "incident_types": ["DATABASE-01", "AUTH-01"],
    })
    assert pat_id is not None
    patterns = fs.search_patterns("auth")
    assert len(patterns) >= 1

    # 3. Procedural Store Protocol
    stat = fs.record_outcome(
        signature="DATABASE-01:DATABASE_TIMEOUT",
        strategy="scale_service",
        success=True,
    )
    assert stat["total_executions"] == 1
    assert stat["success_count"] == 1

    all_stats = fs.get_strategy_stats("DATABASE-01:DATABASE_TIMEOUT")
    assert "scale_service" in all_stats
    assert all_stats["scale_service"]["success_rate"] == 1.0
