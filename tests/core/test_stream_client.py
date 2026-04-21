"""StreamClient loopback + reconnect behaviour against a real core subprocess."""

import asyncio
from pathlib import Path

import pytest

from palio_bot.core_client.stream_client import (
    _RECONNECT_BUDGET_S,
    StreamClient,
    StreamClientFatal,
)
from palio_bot.core_client.subprocess import CoreProcess
from palio_bot.stream.events import Event, UserMessageEvent


class CollectingConsumer:
    def __init__(self):
        self.received: list[Event] = []
        self.any_received = asyncio.Event()

    def filter(self, event: Event) -> bool:
        return True

    async def consume(self, event: Event) -> None:
        self.received.append(event)
        self.any_received.set()


def _seed_data_dir(data_dir: Path) -> None:
    (data_dir / "palio.json").write_text(
        '{"competition_name":"t","villages":[],"villages_colors":{},'
        '"games":[],"non_game_events":[]}'
    )
    (data_dir / "palio_games_status.json").write_text(
        '{"game_scores":{},"last_updated":"2026-04-20T00:00:00Z"}'
    )
    (data_dir / "leaderboard.json").write_text(
        '{"villages":[],"palio_leaderboard":{},"game_leaderboards":{}}'
    )


@pytest.fixture
def running_core(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    _seed_data_dir(data)
    with CoreProcess(data_dir=data) as core:
        yield core


async def _wait_for(event: asyncio.Event, timeout: float = 5.0) -> None:
    await asyncio.wait_for(event.wait(), timeout=timeout)


async def test_stream_client_loopback(running_core):
    """Publisher's own event comes back through the WS."""
    client = StreamClient(running_core.base_url)
    consumer = CollectingConsumer()
    client.add_consumer(consumer)

    await client.start_processing()
    try:
        await client.put_event(UserMessageEvent(session_id="s1", content="hi"))
        await _wait_for(consumer.any_received)
    finally:
        await client.stop_processing()

    types = [e.type for e in consumer.received]
    assert "UserMessageEvent" in types


async def test_stream_client_fanout_between_clients(running_core):
    """Two clients both see each other's publishes."""
    a = StreamClient(running_core.base_url)
    b = StreamClient(running_core.base_url)
    ca, cb = CollectingConsumer(), CollectingConsumer()
    a.add_consumer(ca)
    b.add_consumer(cb)

    await a.start_processing()
    await b.start_processing()
    try:
        await a.put_event(UserMessageEvent(session_id="s1", content="from-a"))
        await _wait_for(cb.any_received)
    finally:
        await a.stop_processing()
        await b.stop_processing()

    assert any(
        e.type == "UserMessageEvent" and getattr(e, "content", "") == "from-a"
        for e in cb.received
    )


async def test_stream_client_fatal_when_core_never_available(tmp_path: Path):
    """No core reachable → reconnect budget exhausts → fatal."""
    fatal_seen = asyncio.Event()

    def on_fatal(_exc: BaseException) -> None:
        fatal_seen.set()

    client = StreamClient(
        "http://127.0.0.1:1",  # unreachable
        on_fatal=on_fatal,
    )
    # start_processing awaits the initial connection — it should time out
    # before the run task raises fatal (run task has the full budget).
    with pytest.raises(Exception):
        await client.start_processing()

    # Run task should eventually fire on_fatal within the reconnect budget.
    await asyncio.wait_for(fatal_seen.wait(), timeout=_RECONNECT_BUDGET_S + 5.0)
    await client.stop_processing()
