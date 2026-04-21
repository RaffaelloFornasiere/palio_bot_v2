"""WebSocket endpoint for event pub/sub.

One subscriber per connection. Core publishes events onto the bus (starting
Phase 2); in Phase 1 the socket accepts and stays open with zero traffic so
clients can verify the contract.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/events")
async def events_ws(websocket: WebSocket) -> None:
    event_bus = websocket.app.state.event_bus
    await websocket.accept()
    sub_id, queue = event_bus.subscribe()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.debug("events_ws: client disconnected")
    except Exception:
        logger.exception("events_ws: unexpected error")
    finally:
        event_bus.unsubscribe(sub_id)
