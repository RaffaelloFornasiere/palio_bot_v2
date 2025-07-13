"""Event stream for distributing events to consumers.

Simplified async stream without immediate/queued distinction.
"""
import asyncio
import logging
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .interfaces import Consumer
    from .events import Event

logger = logging.getLogger(__name__)


class Stream:
    """Central event distribution system."""
    
    def __init__(self):
        self.consumers: List['Consumer'] = []
        self.event_queue: asyncio.Queue['Event'] = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown: bool = False
        
    def add_consumer(self, consumer: 'Consumer') -> None:
        """Add a consumer to process events."""
        self.consumers.append(consumer)
        logger.info(f"Added consumer: {consumer.__class__.__name__}")
        
    def remove_consumer(self, consumer: 'Consumer') -> None:
        """Remove a consumer from the stream."""
        if consumer in self.consumers:
            self.consumers.remove(consumer)
            logger.info(f"Removed consumer: {consumer.__class__.__name__}")
        
    async def put_event(self, event: 'Event') -> None:
        """Put an event into the stream."""
        await self.event_queue.put(event)
        logger.debug(f"Event queued: {event.type} (session: {event.session_id})")
        
    async def start_processing(self) -> None:
        """Start processing events."""
        if self._processing_task is None or self._processing_task.done():
            logger.info("Starting event processing loop")
            self._shutdown = False
            self._processing_task = asyncio.create_task(self._process_events())
            
    async def stop_processing(self) -> None:
        """Stop processing events gracefully."""
        logger.info("Stopping event processing loop")
        self._shutdown = True
        
        # Put a sentinel event to wake up the processing loop
        from .events import Event
        sentinel = Event(type="_StopEvent", session_id="system")
        await self.event_queue.put(sentinel)
        
        # Wait for processing task to complete
        if self._processing_task and not self._processing_task.done():
            await self._processing_task
            
        logger.info("Event processing loop stopped")
        
    async def _process_events(self) -> None:
        """Process events from queue."""
        logger.info("Event processing loop started")
        
        while not self._shutdown:
            try:
                event = await self.event_queue.get()
                
                # Check for shutdown sentinel
                if event.type == "_StopEvent":
                    self.event_queue.task_done()
                    break
                
                logger.debug(f"Processing event: {event.type}")
                
                # Send to all consumers
                for consumer in self.consumers:
                    try:
                        if consumer.filter(event):
                            logger.debug(
                                f"Dispatching {event.type} to {consumer.__class__.__name__}"
                            )
                            await consumer.consume(event)
                    except Exception as e:
                        logger.error(
                            f"Error in consumer {consumer.__class__.__name__}: {e}",
                            exc_info=True
                        )
                        
                self.event_queue.task_done()
                
            except asyncio.CancelledError:
                logger.info("Event processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in event processing loop: {e}", exc_info=True)