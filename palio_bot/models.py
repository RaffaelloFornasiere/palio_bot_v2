"""Pydantic models for the palio bot system."""

from datetime import datetime
from typing import Any, Literal, Callable
from pydantic import BaseModel, Field


class CacheControl(BaseModel):
    type: Literal["ephemeral"] = "ephemeral"


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str
    cache_control: CacheControl | None = None


class ToolUseContent(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    tool_name: str
    tool_parameters: Any
    tool_use_id: str


class ToolResultContent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_result: "ToolResult"
    tool_use_id: str


Role = Literal["user", "assistant", "event"]


class Message(BaseModel):
    """A single message in the conversation, from either user or assistant."""

    id: int | None = Field(default=None)
    creation_time: datetime = Field(default_factory=datetime.now)
    role: Role
    content: list[TextContent | ToolUseContent | ToolResultContent]

    @classmethod
    def text(cls, *, role: Role, text: str) -> "Message":
        """Convenience method to create a simple text message."""
        return cls(role=role, content=[TextContent(text=text)])

    @classmethod
    def tool_use(
        cls, *, role: Role, tool_name: str, tool_parameters: Any, tool_use_id: str
    ) -> "Message":
        """Convenience method to create a tool use message."""
        return cls(
            role=role,
            content=[
                ToolUseContent(
                    tool_name=tool_name,
                    tool_parameters=tool_parameters,
                    tool_use_id=tool_use_id,
                )
            ],
        )

    @classmethod
    def tool_result(
        cls, *, role: Role, tool_result: "ToolResult", tool_use_id: str
    ) -> "Message":
        """Convenience method to create a tool result message."""
        return cls(
            role=role,
            content=[
                ToolResultContent(tool_result=tool_result, tool_use_id=tool_use_id)
            ],
        )


class ToolResult(BaseModel):
    """Result returned by a tool execution."""
    
    success: bool
    data: Any = None
    error: str | None = None
    message: str | None = None


class Tool(BaseModel):
    """Represents a tool that can be called by the LLM."""
    
    name: str
    description: str
    parameters_schema: dict[str, Any]  # JSON Schema for the parameters
    function: Callable[..., ToolResult] = Field(exclude=True)  # Exclude from serialization
    
    class Config:
        arbitrary_types_allowed = True
    
    def call(self, **kwargs) -> ToolResult:
        """Call the tool function with the given parameters."""
        return self.function(**kwargs)


class Session(BaseModel):
    """Represents a conversation session."""
    
    id: str
    creation_time: datetime = Field(default_factory=datetime.now)
    messages: list[Message] = Field(default_factory=list)
    
    def add_message(self, message: Message) -> None:
        """Add a message to the session."""
        self.messages.append(message)