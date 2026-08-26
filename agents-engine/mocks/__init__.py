"""
AEGIS Ω — Mocks Package
Provides event simulation, mock data generators, and chaos scenarios.
"""

from .event_generator import (
    EventType,
    Severity,
    SystemEvent,
    EventGenerator,
    generate_cascading_failure,
    generate_event,
)

__all__ = [
    "EventType",
    "Severity",
    "SystemEvent",
    "EventGenerator",
    "generate_cascading_failure",
    "generate_event",
]
