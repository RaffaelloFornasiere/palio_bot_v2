"""Producer and Consumer interfaces for the unified event stream."""
from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .events import Event


class Producer:
    """Mixin for services that produce events onto the stream."""

    def __init__(self, stream: Any):
        self.stream = stream

    async def produce(self, event: "Event") -> None:
        await self.stream.put_event(event)


class Consumer(Protocol):
    """Interface for event consumers."""

    def filter(self, event: "Event") -> bool: ...

    async def consume(self, event: "Event") -> None: ...