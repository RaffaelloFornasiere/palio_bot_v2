"""Event models for the Palio Bot event system.

All events inherit from `Event` and carry a `type: Literal[...]` so Pydantic
can serialize/deserialize them via the `AnyEvent` discriminated union that
travels across the WS between adapters and core.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
import uuid

from pydantic import BaseModel, Field, TypeAdapter

from palio_bot.agent.models import Message, ToolResult, TokenUsage


class Event(BaseModel):
    """Base event class."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    creation_time: datetime = Field(default_factory=datetime.now)
    type: str
    session_id: str

    def serialized_data(self) -> Dict[str, Any]:
        return self.model_dump()


# ---------- Agent-side events (emitted by the adapter System) ----------

class UserMessageEvent(Event):
    type: Literal["UserMessageEvent"] = "UserMessageEvent"
    content: str


class AgentUpdateEvent(Event):
    type: Literal["AgentUpdateEvent"] = "AgentUpdateEvent"
    message: Message


class ToolUseEvent(Event):
    type: Literal["ToolUseEvent"] = "ToolUseEvent"
    tool_name: str
    parameters: Dict[str, Any]


class ToolResultEvent(Event):
    type: Literal["ToolResultEvent"] = "ToolResultEvent"
    tool_name: str
    result: ToolResult


class AgentCompleteEvent(Event):
    type: Literal["AgentCompleteEvent"] = "AgentCompleteEvent"
    total_token_usage: Optional[TokenUsage] = None


class AgentCancelledEvent(Event):
    type: Literal["AgentCancelledEvent"] = "AgentCancelledEvent"
    reason: str


class ErrorEvent(Event):
    type: Literal["ErrorEvent"] = "ErrorEvent"
    error: str
    traceback: Optional[str] = None


# ---------- Core-side events (emitted by palio-core) ----------

class FileChangedEvent(Event):
    type: Literal["file_changed"] = "file_changed"
    file: str
    version: str


class LockAcquiredEvent(Event):
    type: Literal["lock_acquired"] = "lock_acquired"
    file: str


class LockReleasedEvent(Event):
    type: Literal["lock_released"] = "lock_released"
    file: str


class SessionStartedEvent(Event):
    type: Literal["session_started"] = "session_started"
    label: str


class SessionCommittedEvent(Event):
    type: Literal["session_committed"] = "session_committed"
    files: List[str] = Field(default_factory=list)
    locks_released: List[str] = Field(default_factory=list)


class SessionDiscardedEvent(Event):
    type: Literal["session_discarded"] = "session_discarded"
    locks_released: List[str] = Field(default_factory=list)


# ---------- Discriminated union for wire (de)serialization ----------

AnyEvent = Annotated[
    Union[
        UserMessageEvent,
        AgentUpdateEvent,
        ToolUseEvent,
        ToolResultEvent,
        AgentCompleteEvent,
        AgentCancelledEvent,
        ErrorEvent,
        FileChangedEvent,
        LockAcquiredEvent,
        LockReleasedEvent,
        SessionStartedEvent,
        SessionCommittedEvent,
        SessionDiscardedEvent,
    ],
    Field(discriminator="type"),
]

EventAdapter: TypeAdapter[Event] = TypeAdapter(AnyEvent)


def parse_event(payload: Dict[str, Any]) -> Event:
    """Parse a wire-format dict into the correct Event subclass."""
    return EventAdapter.validate_python(payload)


def dump_event(event: Event) -> Dict[str, Any]:
    """Serialize an Event to a wire-format dict (JSON-compatible types)."""
    return event.model_dump(mode="json")
