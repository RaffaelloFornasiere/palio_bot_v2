"""CLI Consumer for displaying events in the terminal."""

import json
import logging
from typing import Optional, Dict, List
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from palio_bot.stream.events import (
    Event, UserMessageEvent, AgentUpdateEvent, ToolUseEvent,
    ToolResultEvent, AgentCompleteEvent, ErrorEvent
)
from palio_bot.agent.models import TextContent

logger = logging.getLogger(__name__)


class CLIConsumer:
    """Consumer that displays events in the terminal with rich formatting."""
    
    def __init__(self):
        self.current_session_id: Optional[str] = None
        self.console = Console()
        self.accumulated_text: dict[str, str] = {}  # session_id -> accumulated text
        self.conversation_history: dict[str, list[str]] = {}  # session_id -> list of conversation parts
        logger.info("CLIConsumer initialized")
        
    def filter(self, event: Event) -> bool:
        """Process events for current session."""
        # If we don't have a session ID yet, accept the first event and set our session ID
        if self.current_session_id is None:
            logger.info(f"No current session ID, accepting event from session {event.session_id[:8]}... and setting as current")
            self.current_session_id = event.session_id
            return True
            
        should_process = event.session_id == self.current_session_id
        if not should_process:
            logger.debug(f"Filtering out event {event.type} for session {event.session_id[:8]}... (current: {self.current_session_id[:8] if self.current_session_id else 'None'})")
        return should_process
        
    async def consume(self, event: Event) -> None:
        """Display event in terminal with rich formatting."""
        logger.debug(f"CLIConsumer consuming event: {event.type}")
        
        try:
            if isinstance(event, UserMessageEvent):
                self._display_user_message(event)

            elif isinstance(event, AgentUpdateEvent):
                self._display_agent_update(event)

            elif isinstance(event, ToolUseEvent):
                self._display_tool_use(event)

            elif isinstance(event, ToolResultEvent):
                self._display_tool_result(event)

            elif isinstance(event, AgentCompleteEvent):
                # Clean up accumulated text and conversation history for this session
                if event.session_id in self.accumulated_text:
                    del self.accumulated_text[event.session_id]
                if event.session_id in self.conversation_history:
                    del self.conversation_history[event.session_id]

            elif isinstance(event, ErrorEvent):
                self._display_error(event)
                
            logger.debug(f"CLIConsumer finished consuming {event.type}")
            
        except Exception as e:
            logger.error(f"Error in CLIConsumer.consume: {e}", exc_info=True)
            self.console.print(f"[red]Error displaying event: {e}[/red]")
    
    def _display_user_message(self, event: UserMessageEvent) -> None:
        """Display user message."""
        self.console.print()
        self.console.print(
            Panel(
                event.content,
                title="[bold blue]👤 User[/bold blue]",
                border_style="blue"
            )
        )
    
    def _display_agent_update(self, event: AgentUpdateEvent) -> None:
        """Display agent update (text or tool use) with text accumulation."""
        msg = event.message
        session_id = event.session_id
        
        # Extract text content
        text_parts = []
        for content in msg.content:
            if isinstance(content, TextContent):
                text_parts.append(content.text)
        
        if text_parts:
            # Accumulate text across multiple AgentUpdateEvents
            new_text = "\n".join(text_parts)
            
            if session_id in self.accumulated_text:
                # Add to existing text with separator
                self.accumulated_text[session_id] += "\n\n" + new_text
            else:
                # First text for this session
                self.accumulated_text[session_id] = new_text
            
            # Add to conversation history
            if session_id not in self.conversation_history:
                self.conversation_history[session_id] = []
            self.conversation_history[session_id].append(f"**Assistant:** {new_text}")
            
            # Display full conversation
            self._display_full_conversation(session_id)
    
    def _display_tool_use(self, event: ToolUseEvent) -> None:
        """Display tool use details."""
        session_id = event.session_id
        
        # Add to conversation history
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        
        tool_text = f"🔧 **Using tool:** `{event.tool_name}`"
        if event.parameters:
            # Show simplified parameters for history
            params_preview = self._format_params_simple(event.parameters)
            if params_preview:
                tool_text += f"\n   {params_preview}"
        
        self.conversation_history[session_id].append(tool_text)
        
        # Display full conversation
        self._display_full_conversation(session_id)
    
    def _display_tool_result(self, event: ToolResultEvent) -> None:
        """Display tool result."""
        session_id = event.session_id
        result = event.result
        
        # Add to conversation history
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        
        if result.success:
            result_text = f"   ✅ **Success:** {result.data}"
        else:
            result_text = f"   ❌ **Error:** {result.error}"
        
        self.conversation_history[session_id].append(result_text)
        
        # Display full conversation
        self._display_full_conversation(session_id)
    
    def _display_error(self, event: ErrorEvent) -> None:
        """Display error event."""
        self.console.print()
        self.console.print(
            Panel(
                f"[red]❌ Error: {event.error}[/red]",
                title="[bold red]System Error[/bold red]",
                border_style="red"
            )
        )
        if event.traceback:
            self.console.print(f"[dim]{event.traceback}[/dim]")
    
    def _display_full_conversation(self, session_id: str) -> None:
        """Display the full conversation history for a session."""
        if session_id not in self.conversation_history:
            return
            
        # Build conversation text
        conversation_text = "\n\n".join(self.conversation_history[session_id])
        
        self.console.print()
        self.console.print(
            Panel(
                Markdown(conversation_text),
                title="[bold green]🤖 Assistant[/bold green]",
                border_style="green"
            )
        )
    
    def _format_params_simple(self, parameters: dict) -> str:
        """Format parameters for simple display in conversation history."""
        if not parameters:
            return ""
        
        # Show key parameters in a compact format
        parts = []
        
        if "path" in parameters:
            parts.append(f"path: `{parameters['path']}`")
        elif "json_path" in parameters:
            parts.append(f"path: `{parameters['json_path']}`")
        
        if "value" in parameters:
            value = parameters["value"]
            if isinstance(value, (dict, list)):
                parts.append("value: [complex object]")
            else:
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                parts.append(f"value: `{value_str}`")
        
        return " | ".join(parts[:2])  # Limit to 2 parts for brevity