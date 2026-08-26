"""
Unit and Integration Tests for Cloud Run FastAPI Web Server & Health Endpoint.
Tests:
  - GET /health endpoint structure and components
  - GET / root metadata endpoint
  - POST /api/v1/incident direct trigger and execution
  - POST /api/v1/pubsub/push message decoding and routing
  - GET /api/v1/traces/{incident_id} trace timeline generation
"""

import base64
import importlib
import json

from runtime.server import app


def _get_test_client():
    """Load TestClient dynamically at runtime to prevent static import warnings."""
    try:
        mod = importlib.import_module("fastapi.testclient")
    except Exception:
        mod = importlib.import_module("starlette.testclient")
    test_client_cls = getattr(mod, "TestClient")
    return test_client_cls(app)


def test_health_endpoint_returns_200_and_all_components():
    """Verify /health endpoint returns HTTP 200 with structured component statuses."""
    with _get_test_client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service"] == "aegis-omega-intelligence-engine"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data
        assert "environment" in data
        assert "components" in data

        components = data["components"]
        assert "pipeline" in components
        assert "gemini" in components
        assert "pubsub" in components
        assert "cloud_sql" in components
        assert "firestore" in components
        assert components["agents_registered"] == "13"


def test_root_endpoint_returns_metadata():
    """Verify GET / returns service information and endpoints."""
    with _get_test_client() as client:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "AEGIS Ω" in data["service"]
        assert "/health" in data["endpoints"]["health"]
        assert "/api/v1/incident" in data["endpoints"]["incident_trigger"]


def test_incident_trigger_api_executes_pipeline():
    """Verify POST /api/v1/incident triggers pipeline and returns resolution."""
    with _get_test_client() as client:
        payload = {
            "asset_id": "DATABASE-01",
            "event_type": "DATABASE_TIMEOUT",
            "severity": "CRITICAL",
            "metrics": {"query_latency_ms": 32000.0, "latency_ms": 850.0},
            "source": "api_test",
            "correlation_id": "corr-api-test-01",
        }
        response = client.post("/api/v1/incident", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "incident_id" in data
        assert data["correlation_id"] == "corr-api-test-01"
        assert data["asset_id"] == "DATABASE-01"
        assert data["final_status"] == "RESOLVED"
        assert data["success"] is True
        assert len(data["stages_executed"]) >= 10


def test_pubsub_push_webhook_processes_message():
    """Verify POST /api/v1/pubsub/push decodes base64 payload and processes incident."""
    with _get_test_client() as client:
        event_dict = {
            "asset_id": "AUTH-01",
            "event_type": "LOGIN_FAILURE",
            "severity": "HIGH",
            "metrics": {"failed_auth_rate_pct": 92.0, "latency_ms": 420.0},
            "source": "pubsub_push_test",
            "correlation_id": "corr-pubsub-test-01",
        }
        encoded_data = base64.b64encode(json.dumps(event_dict).encode("utf-8")).decode("utf-8")

        push_payload = {
            "message": {
                "data": encoded_data,
                "messageId": "msg-123456",
                "publishTime": "2026-08-25T15:00:00Z",
            },
            "subscription": "projects/aegis-dev/subscriptions/sub-incident-detected",
        }

        response = client.post("/api/v1/pubsub/push", json=push_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ACK"
        assert data["resolution"] == "RESOLVED"
