"""Tests for the event Stream: fan-out and consumer error isolation."""

import asyncio

import pytest

from palio_bot.stream.events import Event, UserMessageEvent
from palio_bot.stream.interfaces import Consumer
from palio_bot.stream.stream import Stream


class CollectingConsumer:
    """Consumer that records every event it processes."""

    def __init__(self, accept_type: str | None = None):
        self.accept_type = accept_type
        self.received: list[Event] = []

    def filter(self, event: Event) -> bool:
        return self.accept_type is None or event.type == self.accept_type

    async def consume(self, event: Event) -> None:
        self.received.append(event)


class ExplodingConsumer:
    """Consumer that raises on every event."""

    def filter(self, event: Event) -> bool:
        return True

    async def consume(self, event: Event) -> None:
        raise RuntimeError("consumer exploded")


async def _drain(stream: Stream, expected_events: int, timeout: float = 2.0) -> None:
    """Wait up to `timeout` seconds for the stream to have processed expected_events."""
    deadline = asyncio.get_event_loop().time() + timeout
    while stream._events_processed < expected_events:
        if asyncio.get_event_loop().time() > deadline:
            raise TimeoutError(f"Stream processed {stream._events_processed}/{expected_events}")
        await asyncio.sleep(0.01)


async def test_event_fanout_to_multiple_consumers():
    stream = Stream()
    c1, c2 = CollectingConsumer(), CollectingConsumer()
    stream.add_consumer(c1)
    stream.add_consumer(c2)

    await stream.start_processing()
    try:
        evt = UserMessageEvent(session_id="s1", content="hi")
        await stream.put_event(evt)
        await _drain(stream, 1)

        assert len(c1.received) == 1
        assert len(c2.received) == 1
        assert c1.received[0].id == evt.id
    finally:
        await stream.stop_processing()


async def test_consumer_filter_is_respected():
    stream = Stream()
    accepting = CollectingConsumer(accept_type="UserMessageEvent")
    rejecting = CollectingConsumer(accept_type="NonExistentEvent")
    stream.add_consumer(accepting)
    stream.add_consumer(rejecting)

    await stream.start_processing()
    try:
        await stream.put_event(UserMessageEvent(session_id="s1", content="hi"))
        await _drain(stream, 1)

        assert len(accepting.received) == 1
        assert len(rejecting.received) == 0
    finally:
        await stream.stop_processing()


async def test_consumer_exception_does_not_affect_others():
    stream = Stream()
    good = CollectingConsumer()
    bad = ExplodingConsumer()
    stream.add_consumer(bad)
    stream.add_consumer(good)

    await stream.start_processing()
    try:
        await stream.put_event(UserMessageEvent(session_id="s1", content="hi"))
        await _drain(stream, 1)

        assert len(good.received) == 1
    finally:
        await stream.stop_processing()
