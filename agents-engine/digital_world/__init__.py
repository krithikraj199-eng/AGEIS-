"""
Digital World Module for AEGIS Ω Intelligence Engine.
Exposes Member 1's Digital World interfaces:
1. Event Stream
2. Metrics API
3. Dependency Graph API
4. Historical Incident API
5. Action API
6. Chaos Injection & Test Hooks
"""

from .models import (
    ActionResult,
    DigitalWorldEvent,
    DigitalWorldEventType,
    DigitalWorldSeverity,
    HistoricalIncidentRecord,
    MetricReading,
)
from .client import DigitalWorldClient, get_digital_world_client
from .metrics import MetricsAPI
from .dependency import DependencyGraphAPI
from .history import HistoryAPI
from .actions import ActionAPI
from .chaos import ChaosEngine

__all__ = [
    "DigitalWorldClient",
    "get_digital_world_client",
    "DigitalWorldEvent",
    "DigitalWorldEventType",
    "DigitalWorldSeverity",
    "MetricReading",
    "HistoricalIncidentRecord",
    "ActionResult",
    "MetricsAPI",
    "DependencyGraphAPI",
    "HistoryAPI",
    "ActionAPI",
    "ChaosEngine",
]
