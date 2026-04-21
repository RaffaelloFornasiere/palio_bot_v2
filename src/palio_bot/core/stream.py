"""Core broker for the unified event stream.

Each subscriber owns an asyncio.Queue. Broadcast is non-blocking — when a
subscriber's queue is full we drop the event with a warning (resilience
over completeness; slow clients cannot stall the broker).

Accepts typed `Event` objects; fans out the original instance. Callers
serialize once per network consumer (WS handler).
"""

import asyncio
import logging
import uuid
from typing import Dict

from palio_bot.stream.events import Event

logger = logging.getLogger(__name__)


class Stream:
    def __init__(self, queue_maxsize: int = 256) -> None:
        self._subscribers: Dict[str, asyncio.Queue] = {}
        self._queue_maxsize = queue_maxsize

    def subscribe(self) -> tuple[str, asyncio.Queue]:
        sub_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_maxsize)
        self._subscribers[sub_id] = queue
        logger.debug(
            "core.stream: subscriber %s attached (total=%d)",
            sub_id,
            len(self._subscribers),
        )
        return sub_id, queue

    def unsubscribe(self, sub_id: str) -> None:
        if self._subscribers.pop(sub_id, None) is not None:
            logger.debug(
                "core.stream: subscriber %s detached (remaining=%d)",
                sub_id,
                len(self._subscribers),
            )

    def broadcast(self, event: Event) -> None:
        """Fan out to every subscriber; drops events on full queues."""
        for sub_id, queue in list(self._subscribers.items()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "core.stream: dropping event for subscriber %s (queue full)",
                    sub_id,
                )

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
