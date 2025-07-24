"""Event models for the Palio Bot event system.

Using Literal types pattern inspired by sage_v2 for type safety without enums.
"""
from typing import Literal, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from palio_bot.agent.models import Message, ToolResult, TokenUsage


class Event(BaseModel):
    """Base event class using Literal types pattern."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    creation_time: datetime = Field(default_factory=datetime.now)
    type: str  # Will be overridden by Literal in subclasses
    session_id: str
    
    def serialized_data(self) -> Dict[str, Any]:
        """Convert event data for serialization."""
        return self.model_dump()


class UserMessageEvent(Event):
    """Event emitted when user sends a message."""
    type: Literal["UserMessageEvent"] = "UserMessageEvent"
    content: str


class AgentUpdateEvent(Event):
    """Event emitted when agent produces an update (text or tool use)."""
    type: Literal["AgentUpdateEvent"] = "AgentUpdateEvent"
    message: Message  # Contains text or tool use/result


class ToolUseEvent(Event):
    """Event emitted when agent decides to use a tool."""
    type: Literal["ToolUseEvent"] = "ToolUseEvent"
    tool_name: str
    parameters: Dict[str, Any]


class ToolResultEvent(Event):
    """Event emitted when tool execution completes."""
    type: Literal["ToolResultEvent"] = "ToolResultEvent"
    tool_name: str
    result: ToolResult


class AgentCompleteEvent(Event):
    """Event emitted when agent completes processing."""
    type: Literal["AgentCompleteEvent"] = "AgentCompleteEvent"
    total_token_usage: Optional[TokenUsage] = None


class AgentCancelledEvent(Event):
    """Event emitted when agent processing is cancelled."""
    type: Literal["AgentCancelledEvent"] = "AgentCancelledEvent"
    reason: str


class ErrorEvent(Event):
    """Event emitted when an error occurs."""
    type: Literal["ErrorEvent"] = "ErrorEvent"
    error: str
    traceback: Optional[str] = None