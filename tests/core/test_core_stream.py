"""Bidirectional /events WS: publish loopback, fan-out, bad-frame handling."""

import pytest
from starlette.websockets import WebSocketDisconnect


def _publish_frame(event: dict) -> dict:
    return {"kind": "publish", "event": event}


def _user_event(session_id: str, content: str) -> dict:
    return {
        "type": "UserMessageEvent",
        "session_id": session_id,
        "content": content,
    }


def test_publish_loopback(core_client):
    """Publisher receives its own event back."""
    with core_client.websocket_connect("/events") as ws:
        ws.send_json(_publish_frame(_user_event("s1", "hello")))
        frame = ws.receive_json()

    assert frame["kind"] == "event"
    assert frame["event"]["type"] == "UserMessageEvent"
    assert frame["event"]["session_id"] == "s1"
    assert frame["event"]["content"] == "hello"


def test_publish_fanout_to_multiple_subscribers(core_client):
    """Two subscribers both receive the published event."""
    with (
        core_client.websocket_connect("/events") as ws_a,
        core_client.websocket_connect("/events") as ws_b,
    ):
        ws_a.send_json(_publish_frame(_user_event("s1", "ping")))
        frame_a = ws_a.receive_json()
        frame_b = ws_b.receive_json()

    assert frame_a["event"]["content"] == "ping"
    assert frame_b["event"]["content"] == "ping"


def test_bad_frame_closes_socket(core_client):
    """Non-publish frames close the WS with an error code."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with core_client.websocket_connect("/events") as ws:
            ws.send_json({"kind": "nope"})
            ws.receive_json()
    assert exc.value.code in (1003, 1007)


def test_unknown_event_type_closes_socket(core_client):
    """Event with a type outside the discriminated union is rejected."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with core_client.websocket_connect("/events") as ws:
            ws.send_json(_publish_frame({"type": "NotARealEvent", "session_id": "s1"}))
            ws.receive_json()
    assert exc.value.code in (1003, 1007)


def test_published_event_travels_after_core_event(core_client):
    """Loopback works even after core itself broadcasts (session_started)."""
    with core_client.websocket_connect("/events") as ws:
        # Trigger a core-side event on a different socket via HTTP.
        res = core_client.post("/api/sessions", json={"label": "cli"})
        assert res.status_code == 200

        # ws should see the session_started event first.
        first = ws.receive_json()
        assert first["event"]["type"] == "session_started"

        # Now publish ours and receive it.
        ws.send_json(_publish_frame(_user_event("s1", "hi")))
        second = ws.receive_json()
        assert second["event"]["type"] == "UserMessageEvent"
