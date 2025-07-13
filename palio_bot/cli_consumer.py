"""CLI Consumer for displaying events in the terminal."""

import json
from typing import Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from .events import (
    Event, UserMessageEvent, AgentUpdateEvent, ToolUseEvent,
    ToolResultEvent, AgentCompleteEvent, ErrorEvent
)
from .models import TextContent, ToolUseContent


class CLIConsumer:
    """Consumer that displays events in the terminal with rich formatting."""
    
    def __init__(self):
        self.current_session_id: Optional[str] = None
        self.console = Console()
        
    def filter(self, event: Event) -> bool:
        """Process events for current session."""
        return event.session_id == self.current_session_id
        
    async def consume(self, event: Event) -> None:
        """Display event in terminal with rich formatting."""
        if isinstance(event, UserMessageEvent):
            self._display_user_message(event)
            
        elif isinstance(event, AgentUpdateEvent):
            self._display_agent_update(event)
                
        elif isinstance(event, ToolUseEvent):
            self._display_tool_use(event)
            
        elif isinstance(event, ToolResultEvent):
            self._display_tool_result(event)
            
        elif isinstance(event, AgentCompleteEvent):
            # Final message already displayed via AgentUpdateEvent
            pass
                
        elif isinstance(event, ErrorEvent):
            self._display_error(event)
    
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
        """Display agent update (text or tool use)."""
        msg = event.message
        
        # Extract text content
        text_parts = []
        for content in msg.content:
            if isinstance(content, TextContent):
                text_parts.append(content.text)
        
        if text_parts:
            # Display assistant text response
            self.console.print()
            text = "\n".join(text_parts)
            # Use Markdown rendering for better formatting
            self.console.print(
                Panel(
                    Markdown(text),
                    title="[bold green]🤖 Assistant[/bold green]",
                    border_style="green"
                )
            )
    
    def _display_tool_use(self, event: ToolUseEvent) -> None:
        """Display tool use details."""
        self.console.print()
        self.console.print(f"[yellow]🔧 Using tool: {event.tool_name}[/yellow]")
        
        if event.parameters:
            # Format parameters as JSON
            params_json = json.dumps(event.parameters, indent=2, ensure_ascii=False)
            syntax = Syntax(params_json, "json", theme="monokai", line_numbers=False)
            self.console.print(Panel(syntax, title="Parameters", border_style="yellow"))
    
    def _display_tool_result(self, event: ToolResultEvent) -> None:
        """Display tool result."""
        result = event.result
        
        if result.success:
            self.console.print(f"[green]   ✅ Success: {result.message}[/green]")
            if result.data:
                # Show data preview if present
                data_str = json.dumps(result.data, indent=2, ensure_ascii=False)
                if len(data_str) > 500:
                    data_str = data_str[:500] + "\n... (truncated)"
                syntax = Syntax(data_str, "json", theme="monokai", line_numbers=False)
                self.console.print(Panel(
                    syntax, 
                    title="Result Data", 
                    border_style="green",
                    expand=False
                ))
        else:
            self.console.print(f"[red]   ❌ Error: {result.error}[/red]")
            if result.data:
                data_str = json.dumps(result.data, indent=2, ensure_ascii=False)
                self.console.print(f"[dim]   {data_str}[/dim]")
    
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