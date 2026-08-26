"""
Google Cloud Pub/Sub Event Bus for AEGIS Ω Intelligence Engine.
Publishes and consumes events across Google Cloud Pub/Sub topics:
- incident.detected
- incident.investigated
- plan.selected
- action.executed
- incident.resolved
"""

import asyncio
import json
import logging
import os
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Union
from pydantic import BaseModel

from runtime.event_bus import DeadLetterRecord, EventBus, EventHandler
from runtime.config import get_settings

logger = logging.getLogger(__name__)


# Required Standard GCP Pub/Sub Topics
GCP_TOPIC_INCIDENT_DETECTED = "incident.detected"
GCP_TOPIC_INCIDENT_INVESTIGATED = "incident.investigated"
GCP_TOPIC_PLAN_SELECTED = "plan.selected"
GCP_TOPIC_ACTION_EXECUTED = "action.executed"
GCP_TOPIC_INCIDENT_RESOLVED = "incident.resolved"

REQUIRED_PUBSUB_TOPICS = [
    GCP_TOPIC_INCIDENT_DETECTED,
    GCP_TOPIC_INCIDENT_INVESTIGATED,
    GCP_TOPIC_PLAN_SELECTED,
    GCP_TOPIC_ACTION_EXECUTED,
    GCP_TOPIC_INCIDENT_RESOLVED,
]

# Mapping internal event topics to public Cloud Pub/Sub topics
TOPIC_MAPPING: Dict[str, str] = {
    "telemetry.raw": GCP_TOPIC_INCIDENT_DETECTED,
    "incident.triage": GCP_TOPIC_INCIDENT_DETECTED,
    "incident.diagnostics": GCP_TOPIC_INCIDENT_INVESTIGATED,
    "incident.evidence": GCP_TOPIC_INCIDENT_INVESTIGATED,
    "incident.topology": GCP_TOPIC_INCIDENT_INVESTIGATED,
    "incident.security_cleared": GCP_TOPIC_INCIDENT_INVESTIGATED,
    "incident.root_cause": GCP_TOPIC_INCIDENT_INVESTIGATED,
    "incident.plan_formulated": GCP_TOPIC_PLAN_SELECTED,
    "incident.counterfactual_validated": GCP_TOPIC_PLAN_SELECTED,
    "incident.risk_evaluated": GCP_TOPIC_PLAN_SELECTED,
    "incident.execution_authorized": GCP_TOPIC_ACTION_EXECUTED,
    "incident.actuated": GCP_TOPIC_ACTION_EXECUTED,
    "incident.verified": GCP_TOPIC_INCIDENT_RESOLVED,
    "incident.resolved": GCP_TOPIC_INCIDENT_RESOLVED,
    "incident.verification_failed": GCP_TOPIC_ACTION_EXECUTED,
}


class GCPPubSubEventBus(EventBus):
    """
    Google Cloud Pub/Sub Event Bus.
    Supports in-process high-speed routing combined with asynchronous GCP Pub/Sub publishing.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        enable_gcp_pubsub: Optional[bool] = None,
        max_queue_size: int = 10000,
        enable_dlq: bool = True,
    ):
        super().__init__(max_queue_size=max_queue_size, enable_dlq=enable_dlq)
        settings = get_settings()
        self.project_id = project_id or settings.gcp_project_id or "aegis-omega-dev"
        self.enable_gcp_pubsub = (
            enable_gcp_pubsub
            if enable_gcp_pubsub is not None
            else settings.enable_gcp_pubsub
        )
        self.topic_prefix = settings.pubsub_topic_prefix
        self._publisher = None
        self._published_messages: List[Dict[str, Any]] = []

        if self.enable_gcp_pubsub:
            self._init_pubsub_client()

    def _init_pubsub_client(self) -> None:
        """Initialize Google Cloud Pub/Sub Publisher Client."""
        try:
            from google.cloud import pubsub_v1
            self._publisher = pubsub_v1.PublisherClient()
            logger.info(f"Initialized Google Cloud Pub/Sub publisher for project: {self.project_id}")
        except Exception as e:
            logger.warning(
                f"Could not initialize google-cloud-pubsub client ({e}). "
                "Operating in resilient local fallback mode."
            )
            self._publisher = None

    def get_topic_path(self, topic_name: str) -> str:
        """Format full GCP topic path: projects/{project_id}/topics/{topic}."""
        full_topic = f"{self.topic_prefix}{topic_name}"
        return f"projects/{self.project_id}/topics/{full_topic}"

    async def publish(self, topic: str, event: Any) -> None:
        """
        Publish event to local in-process subscribers and forward to Google Cloud Pub/Sub.
        """
        # 1. In-process dispatch to local agent subscribers
        await super().publish(topic, event)

        # 2. Forward to Cloud Pub/Sub if mapped and enabled
        mapped_gcp_topic = TOPIC_MAPPING.get(topic)
        if mapped_gcp_topic:
            await self._publish_to_gcp(mapped_gcp_topic, topic, event)

    async def _publish_to_gcp(self, gcp_topic: str, original_topic: str, event: Any) -> None:
        """Serialize and publish event payload to GCP Pub/Sub."""
        payload_dict: Dict[str, Any] = {}
        if hasattr(event, "model_dump"):
            payload_dict = event.model_dump()
        elif hasattr(event, "to_dict"):
            payload_dict = event.to_dict()
        elif isinstance(event, dict):
            payload_dict = event
        else:
            payload_dict = {"raw_payload": str(event)}

        # Add routing metadata
        envelope = {
            "gcp_topic": gcp_topic,
            "original_topic": original_topic,
            "payload": payload_dict,
        }
        self._published_messages.append(envelope)

        if self._publisher and self.enable_gcp_pubsub:
            try:
                data = json.dumps(envelope, default=str).encode("utf-8")
                topic_path = self.get_topic_path(gcp_topic)
                # Run sync publisher call in executor thread
                loop = asyncio.get_running_loop()
                future = self._publisher.publish(topic_path, data, original_topic=original_topic)
                await loop.run_in_executor(None, future.result, 5.0)
                logger.debug(f"Published event to Cloud Pub/Sub topic {topic_path}")
            except Exception as e:
                logger.error(f"Failed to publish to Cloud Pub/Sub topic {gcp_topic}: {e}")

    @property
    def published_gcp_messages(self) -> List[Dict[str, Any]]:
        """Access list of recorded messages published to GCP Pub/Sub."""
        return list(self._published_messages)


# Global singleton instance
_global_event_bus: Optional[GCPPubSubEventBus] = None


def get_pubsub_event_bus() -> GCPPubSubEventBus:
    """Retrieve or initialize the global GCPPubSubEventBus singleton."""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = GCPPubSubEventBus()
    return _global_event_bus
