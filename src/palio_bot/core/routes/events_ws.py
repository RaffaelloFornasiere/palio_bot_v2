"""Bidirectional WebSocket endpoint for the unified event stream.

Wire protocol:
- Inbound:  {"kind": "publish", "event": {...}}  — client publishes an event.
- Outbound: {"kind": "event",   "event": {...}}  — core broadcasts to all
  subscribers (including the publisher — pure loopback).

Bad frames close the socket with an invalid-payload code.
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from palio_bot.stream.events import parse_event

logger = logging.getLogger(__name__)
router = APIRouter()

# Close codes (RFC 6455 + app range).
_CLOSE_UNSUPPORTED_DATA = 1003
_CLOSE_INVALID_PAYLOAD = 1007


@router.websocket("/events")
async def events_ws(websocket: WebSocket) -> None:
    stream = websocket.app.state.stream
    await websocket.accept()
    sub_id, queue = stream.subscribe()

    sender = asyncio.create_task(_sender_loop(websocket, queue))
    try:
        while True:
            try:
                frame = await websocket.receive_json()
            except ValueError:
                await websocket.close(code=_CLOSE_INVALID_PAYLOAD)
                return

            kind = frame.get("kind") if isinstance(frame, dict) else None
            if kind != "publish":
                await websocket.close(code=_CLOSE_UNSUPPORTED_DATA)
                return

            raw_event = frame.get("event")
            if not isinstance(raw_event, dict):
                await websocket.close(code=_CLOSE_INVALID_PAYLOAD)
                return

            try:
                event = parse_event(raw_event)
            except ValidationError:
                await websocket.close(code=_CLOSE_INVALID_PAYLOAD)
                return

            stream.broadcast(event)
    except WebSocketDisconnect:
        logger.debug("events_ws: client disconnected")
    except Exception:
        logger.exception("events_ws: unexpected error")
    finally:
        sender.cancel()
        try:
            await sender
        except (asyncio.CancelledError, Exception):
            pass
        stream.unsubscribe(sub_id)


async def _sender_loop(websocket: WebSocket, queue: asyncio.Queue) -> None:
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(
                {"kind": "event", "event": event.model_dump(mode="json")}
            )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.debug("events_ws sender: stopping", exc_info=True)
