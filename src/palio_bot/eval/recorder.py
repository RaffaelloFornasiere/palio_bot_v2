"""Event consumer that captures per-step data for the eval runner."""

from __future__ import annotations

import asyncio
from typing import Any

from palio_bot.agent.models import TextContent
from palio_bot.stream.events import (
    AgentCancelledEvent,
    AgentCompleteEvent,
    AgentUpdateEvent,
    ErrorEvent,
    Event,
    ToolResultEvent,
    ToolUseEvent,
)


class EvalRecorder:
    """Records tool calls, errors, and token usage for the current step.

    Each scenario step resets the recorder via `reset_step()`, runs the
    prompt, then awaits `complete.wait()` to be sure the processing loop
    dispatched the `AgentCompleteEvent` before we read files / diffs.
    """

    def __init__(self):
        self.tool_calls: list[dict[str, Any]] = []
        self.tool_failures: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.total_tokens: int = 0
        self.complete: asyncio.Event = asyncio.Event()
        self.cancelled: bool = False
        self.assistant_texts: list[str] = []

    # --- Consumer protocol ---

    def filter(self, event: Event) -> bool:
        return True

    async def consume(self, event: Event) -> None:
        if isinstance(event, ToolUseEvent):
            self.tool_calls.append({"tool": event.tool_name, "parameters": event.parameters})
        elif isinstance(event, ToolResultEvent) and not event.result.success:
            self.tool_failures.append(
                {"tool": event.tool_name, "error": event.result.error}
            )
        elif isinstance(event, AgentUpdateEvent):
            # Collect assistant text blocks — last one is the final reply.
            text_parts = [
                c.text for c in event.message.content if isinstance(c, TextContent)
            ]
            if text_parts:
                self.assistant_texts.append("\n".join(text_parts))
        elif isinstance(event, AgentCompleteEvent):
            if event.total_token_usage:
                self.total_tokens = event.total_token_usage.total_tokens
            self.complete.set()
        elif isinstance(event, AgentCancelledEvent):
            self.cancelled = True
            self.complete.set()
        elif isinstance(event, ErrorEvent):
            self.errors.append(event.error)
            self.complete.set()

    # --- Helpers ---

    def reset_step(self) -> None:
        self.tool_calls = []
        self.tool_failures = []
        self.errors = []
        self.total_tokens = 0
        self.cancelled = False
        self.complete = asyncio.Event()
        self.assistant_texts = []

    @property
    def final_assistant_text(self) -> str:
        """The last assistant text block seen this step, or '' if none."""
        return self.assistant_texts[-1] if self.assistant_texts else ""
