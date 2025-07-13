"""Telegram Consumer for sending events to Telegram chat."""

import json
from typing import Dict, Any
from telegram import Bot
from telegram.error import TelegramError
import logging

from .events import (
    Event, UserMessageEvent, AgentUpdateEvent, ToolUseEvent,
    ToolResultEvent, AgentCompleteEvent, ErrorEvent
)
from .models import TextContent

logger = logging.getLogger(__name__)


class TelegramConsumer:
    """Consumer that sends events to Telegram chat with progressive updates."""
    
    def __init__(self, bot: Bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self.message_stack: Dict[str, int] = {}  # session_id -> message_id
        self.current_text: Dict[str, str] = {}  # session_id -> accumulated text
        
    def filter(self, event: Event) -> bool:
        """Process all events."""
        return True
        
    async def consume(self, event: Event) -> None:
        """Send or update Telegram messages based on events."""
        try:
            if isinstance(event, UserMessageEvent):
                await self._handle_user_message(event)
                
            elif isinstance(event, ToolUseEvent):
                await self._handle_tool_use(event)
                
            elif isinstance(event, ToolResultEvent):
                await self._handle_tool_result(event)
                
            elif isinstance(event, AgentUpdateEvent):
                await self._handle_agent_update(event)
                
            elif isinstance(event, AgentCompleteEvent):
                await self._handle_agent_complete(event)
                
            elif isinstance(event, ErrorEvent):
                await self._handle_error(event)
                
        except TelegramError as e:
            logger.error(f"Telegram error in consumer: {e}")
    
    async def _handle_user_message(self, event: UserMessageEvent) -> None:
        """Handle user message event - start new conversation."""
        # Send initial processing message
        msg = await self.bot.send_message(
            self.chat_id,
            f"🔄 Processing: {event.content}\n\n⏳ Thinking..."
        )
        self.message_stack[event.session_id] = msg.message_id
        self.current_text[event.session_id] = ""
    
    async def _handle_tool_use(self, event: ToolUseEvent) -> None:
        """Handle tool use event - show tool being used."""
        if event.session_id not in self.message_stack:
            return
            
        # Update message to show tool use
        current = self.current_text.get(event.session_id, "")
        tool_text = f"\n\n🔧 Using tool: `{event.tool_name}`"
        
        if event.parameters:
            # Show key parameters (simplified view)
            params_preview = self._format_parameters(event.parameters)
            if params_preview:
                tool_text += f"\n📝 {params_preview}"
        
        updated_text = current + tool_text
        self.current_text[event.session_id] = updated_text
        
        await self._update_message(event.session_id, updated_text + "\n\n⏳ Processing...")
    
    async def _handle_tool_result(self, event: ToolResultEvent) -> None:
        """Handle tool result event - show result status."""
        if event.session_id not in self.message_stack:
            return
            
        current = self.current_text.get(event.session_id, "")
        
        if event.result.success:
            result_text = f"\n✅ {event.result.message}"
        else:
            result_text = f"\n❌ Error: {event.result.error}"
        
        updated_text = current + result_text
        self.current_text[event.session_id] = updated_text
        
        await self._update_message(event.session_id, updated_text + "\n\n⏳ Thinking...")
    
    async def _handle_agent_update(self, event: AgentUpdateEvent) -> None:
        """Handle agent update - accumulate text responses."""
        if event.session_id not in self.message_stack:
            return
            
        # Extract text content from message
        text_parts = []
        for content in event.message.content:
            if isinstance(content, TextContent):
                text_parts.append(content.text)
        
        if text_parts:
            # This is a text response, store it for final display
            # We'll show it in the complete event
            pass
    
    async def _handle_agent_complete(self, event: AgentCompleteEvent) -> None:
        """Handle completion - show final response."""
        if event.session_id not in self.message_stack:
            return
            
        # Update with final message
        await self._update_message(event.session_id, event.final_message)
        
        # Clean up
        del self.message_stack[event.session_id]
        if event.session_id in self.current_text:
            del self.current_text[event.session_id]
    
    async def _handle_error(self, event: ErrorEvent) -> None:
        """Handle error event."""
        if event.session_id in self.message_stack:
            error_text = f"❌ Error: {event.error}"
            await self._update_message(event.session_id, error_text)
            
            # Clean up
            del self.message_stack[event.session_id]
            if event.session_id in self.current_text:
                del self.current_text[event.session_id]
        else:
            # Send as new message if no existing message
            await self.bot.send_message(
                self.chat_id,
                f"❌ Error: {event.error}"
            )
    
    async def _update_message(self, session_id: str, text: str) -> None:
        """Update existing message with new text."""
        if session_id not in self.message_stack:
            return
            
        try:
            # Telegram has a 4096 character limit for messages
            if len(text) > 4000:
                text = text[:3997] + "..."
                
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_stack[session_id],
                text=text,
                parse_mode="Markdown"
            )
        except TelegramError as e:
            # If edit fails (e.g., text unchanged), ignore
            if "message is not modified" not in str(e).lower():
                logger.error(f"Failed to update message: {e}")
    
    def _format_parameters(self, parameters: Dict[str, Any]) -> str:
        """Format parameters for concise display."""
        # Show only key parameters in a readable format
        if not parameters:
            return ""
            
        # Extract key information based on common parameter names
        parts = []
        
        if "path" in parameters:
            parts.append(f"Path: `{parameters['path']}`")
        elif "json_path" in parameters:
            parts.append(f"Path: `{parameters['json_path']}`")
            
        if "value" in parameters:
            value = parameters["value"]
            if isinstance(value, (dict, list)):
                parts.append("Value: [complex object]")
            else:
                parts.append(f"Value: `{value}`")
                
        if "old_string" in parameters and "new_string" in parameters:
            parts.append(f"Replace: `{parameters['old_string'][:20]}...`")
            
        return " | ".join(parts[:2])  # Limit to 2 items for brevity