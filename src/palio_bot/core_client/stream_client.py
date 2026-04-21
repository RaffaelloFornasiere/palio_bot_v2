"""Async WS client for the unified event stream.

Presents the same surface that the adapter-local `Stream` used to offer
(`add_consumer`, `remove_consumer`, `put_event`, `start_processing`,
`stop_processing`) but routes everything through a WebSocket to
palio-core. Producers publish; everyone (including the publisher)
receives back and dispatches to local consumers — pure loopback, no
local short-circuit.

Reconnect: exponential backoff from 100 ms, doubling to a 5 s cap per
attempt, 30 s total budget. On exhaustion the configured `on_fatal`
callback is invoked (adapter is expected to terminate).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable, List, Optional
from urllib.parse import urlparse, urlunparse

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from palio_bot.stream.events import Event, parse_event
from palio_bot.stream.interfaces import Consumer

logger = logging.getLogger(__name__)


_INITIAL_BACKOFF_S = 0.1
_MAX_BACKOFF_S = 5.0
_RECONNECT_BUDGET_S = 30.0


def _to_ws_url(base_url: str, path: str = "/events") -> str:
    parts = urlparse(base_url)
    scheme = {"http": "ws", "https": "wss"}.get(parts.scheme, parts.scheme)
    return urlunparse((scheme, parts.netloc, path, "", "", ""))


class StreamClientFatal(RuntimeError):
    """Raised when the reconnect budget is exhausted."""


class StreamClient:
    def __init__(
        self,
        core_url: str,
        *,
        token: Optional[str] = None,
        on_fatal: Optional[Callable[[BaseException], None]] = None,
        path: str = "/events",
    ) -> None:
        self._ws_url = _to_ws_url(core_url, path)
        self._headers = {"Authorization": f"Bearer {token}"} if token else None
        self._on_fatal = on_fatal

        self.consumers: List[Consumer] = []
        self._ws: Optional[ClientConnection] = None
        self._connected = asyncio.Event()
        self._shutdown = False
        self._run_task: Optional[asyncio.Task] = None

    # ---------- public API (matches the old Stream) ----------

    def add_consumer(self, consumer: Consumer) -> None:
        self.consumers.append(consumer)
        logger.info("StreamClient: added consumer %s", consumer.__class__.__name__)

    def remove_consumer(self, consumer: Consumer) -> None:
        if consumer in self.consumers:
            self.consumers.remove(consumer)
            logger.info(
                "StreamClient: removed consumer %s", consumer.__class__.__name__
            )

    async def start_processing(self) -> None:
        if self._run_task is None or self._run_task.done():
            self._shutdown = False
            self._run_task = asyncio.create_task(self._run())
            # Wait for the initial connection so the first put_event succeeds.
            await asyncio.wait_for(self._connected.wait(), timeout=_RECONNECT_BUDGET_S)

    async def stop_processing(self) -> None:
        self._shutdown = True
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._run_task is not None and not self._run_task.done():
            try:
                await self._run_task
            except Exception:
                pass

    async def put_event(self, event: Event) -> None:
        """Publish an event to core. It comes back via the receive loop."""
        await self._connected.wait()
        assert self._ws is not None
        frame = {"kind": "publish", "event": event.model_dump(mode="json")}
        try:
            await self._ws.send(json.dumps(frame))
        except ConnectionClosed:
            # Drop into the reconnect path; caller can retry.
            self._connected.clear()
            raise

    # ---------- internals ----------

    async def _run(self) -> None:
        backoff = _INITIAL_BACKOFF_S
        reconnect_started: Optional[float] = None

        while not self._shutdown:
            try:
                async with websockets.connect(
                    self._ws_url, additional_headers=self._headers
                ) as ws:
                    self._ws = ws
                    backoff = _INITIAL_BACKOFF_S
                    reconnect_started = None
                    self._connected.set()
                    logger.info("StreamClient: connected to %s", self._ws_url)
                    await self._receive_loop(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._shutdown:
                    break
                self._connected.clear()
                self._ws = None
                if reconnect_started is None:
                    reconnect_started = time.monotonic()
                elapsed = time.monotonic() - reconnect_started
                if elapsed > _RECONNECT_BUDGET_S:
                    logger.error(
                        "StreamClient: reconnect budget exhausted (%.1fs); fatal",
                        elapsed,
                    )
                    fatal = StreamClientFatal(
                        f"core WS unreachable after {elapsed:.1f}s"
                    )
                    if self._on_fatal is not None:
                        try:
                            self._on_fatal(fatal)
                        except Exception:
                            logger.exception("StreamClient: on_fatal raised")
                    raise fatal from exc
                logger.warning(
                    "StreamClient: disconnected (%s); retrying in %.2fs",
                    exc.__class__.__name__,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_S)

        self._connected.clear()
        self._ws = None
        logger.info("StreamClient: run loop stopped")

    async def _receive_loop(self, ws: ClientConnection) -> None:
        async for raw in ws:
            try:
                frame = json.loads(raw)
            except ValueError:
                logger.warning("StreamClient: bad JSON frame, ignoring")
                continue
            if not isinstance(frame, dict) or frame.get("kind") != "event":
                continue
            try:
                event = parse_event(frame.get("event") or {})
            except Exception:
                logger.warning("StreamClient: could not parse event, ignoring")
                continue
            await self._dispatch(event)

    async def _dispatch(self, event: Event) -> None:
        for consumer in self.consumers:
            try:
                if consumer.filter(event):
                    await consumer.consume(event)
            except Exception:
                logger.exception(
                    "StreamClient: consumer %s raised on %s",
                    consumer.__class__.__name__,
                    event.type,
                )
