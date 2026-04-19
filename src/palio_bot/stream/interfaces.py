"""Producer and Consumer interfaces for the event system.

Following the pattern from sage_v2 with clear separation of concerns.
"""
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from palio_bot.stream import Stream
    from .events import Event


class Producer:
    """Mixin for services that produce events."""
    
    def __init__(self, stream: 'Stream'):
        self.stream = stream
        
    async def produce(self, event: 'Event') -> None:
        """Produce an event to the stream."""
        await self.stream.put_event(event)


class Consumer(Protocol):
    """Interface for event consumers."""
    
    def filter(self, event: 'Event') -> bool:
        """Return True if consumer should process this event."""
        ...
        
    async def consume(self, event: 'Event') -> None:
        """Process an event."""
        ...