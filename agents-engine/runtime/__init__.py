"""
AEGIS Ω — Runtime Engine Package
Provides core infrastructure: configuration, event bus, and LLM clients.
"""

from .config import Settings, get_settings
from .event_bus import EventBus, get_event_bus
from .llm import get_gemini_client

__all__ = [
    "Settings",
    "get_settings",
    "EventBus",
    "get_event_bus",
    "get_gemini_client",
]
