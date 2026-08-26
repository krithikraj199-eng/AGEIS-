"""
In-Memory Pub/Sub Event Bus for AEGIS Ω Intelligence Engine.
Facilitates decoupled, asynchronous communication between agents and system components.
"""

import asyncio
import inspect
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Union
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Type aliases for event handlers
SyncHandler = Callable[[Any], None]
AsyncHandler = Callable[[Any], Coroutine[Any, Any, None]]
EventHandler = Union[SyncHandler, AsyncHandler]


class DeadLetterRecord(BaseModel):
    """Represents an event that failed during handler execution."""
    event: Any
    handler_name: str
    error_message: str
    timestamp: str


class EventBus:
    """
    High-performance in-memory Pub/Sub event bus.
    Supports asynchronous and synchronous subscribers, pattern-matching topics,
    dead-letter logging, and event tracing.
    """

    def __init__(self, max_queue_size: int = 10000, enable_dlq: bool = True):
        self._subscribers: Dict[str, Set[EventHandler]] = {}
        self._all_events_subscribers: Set[EventHandler] = set()
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._enable_dlq = enable_dlq
        self._dead_letter_queue: List[DeadLetterRecord] = []
        self._history: List[Any] = []
        self._history_limit: int = 500
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task] = None

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """
        Subscribe a handler to a specific topic or event type.
        Use topic='*' to subscribe to all events.
        """
        if topic == "*":
            self._all_events_subscribers.add(handler)
        else:
            if topic not in self._subscribers:
                self._subscribers[topic] = set()
            self._subscribers[topic].add(handler)
        logger.debug(f"Subscribed handler '{handler.__name__}' to topic '{topic}'")

    def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from a topic."""
        if topic == "*":
            self._all_events_subscribers.discard(handler)
        elif topic in self._subscribers:
            self._subscribers[topic].discard(handler)
            if not self._subscribers[topic]:
                del self._subscribers[topic]

    async def publish(self, topic: str, event: Any) -> None:
        """
        Publish an event to a topic asynchronously.
        Executes all matching subscribers concurrently.
        """
        self._record_history(event)
        handlers = self._get_matching_handlers(topic)
        if not handlers:
            logger.debug(f"No subscribers for topic '{topic}'")
            return

        tasks = []
        for handler in handlers:
            tasks.append(self._execute_handler(handler, event))

        await asyncio.gather(*tasks, return_exceptions=True)

    def publish_sync(self, topic: str, event: Any) -> None:
        """
        Synchronous publish fallback (dispatches to event loop if running,
        or calls sync handlers directly).
        """
        self._record_history(event)
        handlers = self._get_matching_handlers(topic)
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self._execute_handler(handler, event))
                    except RuntimeError:
                        asyncio.run(self._execute_handler(handler, event))
                else:
                    handler(event)
            except Exception as e:
                self._handle_handler_failure(handler, event, str(e))

    def _get_matching_handlers(self, topic: str) -> List[EventHandler]:
        """Retrieve all handlers matching the given topic plus wildcard subscribers."""
        matched = list(self._all_events_subscribers)
        if topic in self._subscribers:
            matched.extend(self._subscribers[topic])
        return matched

    async def _execute_handler(self, handler: EventHandler, event: Any) -> None:
        """Execute a single handler safely with exception isolation."""
        try:
            if inspect.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.exception(f"Error in event handler '{getattr(handler, '__name__', str(handler))}': {e}")
            self._handle_handler_failure(handler, event, str(e))

    def _handle_handler_failure(self, handler: EventHandler, event: Any, error_msg: str) -> None:
        """Record dead-letter failure if DLQ is enabled."""
        if self._enable_dlq:
            import datetime
            record = DeadLetterRecord(
                event=event,
                handler_name=getattr(handler, "__name__", str(handler)),
                error_message=error_msg,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
            self._dead_letter_queue.append(record)

    def _record_history(self, event: Any) -> None:
        """Keep a rolling history of recent events for telemetry and verification."""
        self._history.append(event)
        if len(self._history) > self._history_limit:
            self._history.pop(0)

    @property
    def history(self) -> List[Any]:
        """Retrieve in-memory event history."""
        return list(self._history)

    @property
    def dead_letter_queue(self) -> List[DeadLetterRecord]:
        """Retrieve dead-letter records."""
        return list(self._dead_letter_queue)

    def clear(self) -> None:
        """Clear all subscribers, history, and DLQ."""
        self._subscribers.clear()
        self._all_events_subscribers.clear()
        self._dead_letter_queue.clear()
        self._history.clear()


# Global Singleton Instance
_default_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Retrieve the global in-memory EventBus singleton."""
    global _default_event_bus
    if _default_event_bus is None:
        _default_event_bus = EventBus()
    return _default_event_bus
