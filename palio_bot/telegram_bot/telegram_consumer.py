"""Telegram Consumer for sending events to Telegram chat."""

from typing import Dict, Any
from telegram import Bot
from telegram.error import TelegramError
import logging

from palio_bot.stream.events import (
    Event, UserMessageEvent, AgentUpdateEvent, ToolUseEvent,
    ToolResultEvent, AgentCompleteEvent, AgentCancelledEvent, ErrorEvent
)
from palio_bot.agent.models import TokenUsage
from palio_bot.agent.models import TextContent

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
                
            elif isinstance(event, AgentCancelledEvent):
                await self._handle_agent_cancelled(event)
                
            elif isinstance(event, ErrorEvent):
                await self._handle_error(event)
                
        except TelegramError as e:
            logger.error(f"Telegram error in consumer: {e}")
    
    async def _handle_user_message(self, event: UserMessageEvent) -> None:
        """Handle user message event - start new conversation."""
        # Send initial processing message
        msg = await self.bot.send_message(
            self.chat_id,
            f"🔄 Processing: {event.content}\n\n⏳ Thinking...",
            parse_mode='HTML'
        )
        self.message_stack[event.session_id] = msg.message_id
        self.current_text[event.session_id] = ""
    
    async def _handle_tool_use(self, event: ToolUseEvent) -> None:
        """Handle tool use event - show tool being used."""
        if event.session_id not in self.message_stack:
            return
            
        # Update message to show tool use
        current = self.current_text.get(event.session_id, "")
        tool_text = f"\n\n🔧 Using tool: <code>{self._escape_html(event.tool_name)}</code>"
        
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
            result_text = f"\n\n✅ Tool executed successfully!"
        else:
            result_text = f"\n❌ Error: {event.result.error}"
        
        updated_text = current + result_text
        self.current_text[event.session_id] = updated_text
        
        await self._update_message(event.session_id, updated_text + "\n\n⏳ Thinking...")
    
    async def _handle_agent_update(self, event: AgentUpdateEvent) -> None:
        """Handle agent update - show text responses in real-time."""
        if event.session_id not in self.message_stack:
            return
            
        # Extract text content from message
        text_parts = []
        for content in event.message.content:
            if isinstance(content, TextContent):
                text_parts.append(content.text)
        
        if text_parts:
            # Add agent response to current text
            current = self.current_text.get(event.session_id, "")
            agent_text = "\n\n🤖 " + "\n".join(text_parts)
            
            # Add token usage if available
            if event.message.token_usage:
                agent_text += f"\n{self._format_token_usage(event.message.token_usage)}"
            
            updated_text = current + agent_text
            self.current_text[event.session_id] = updated_text
            
            await self._update_message(event.session_id, updated_text + "\n\n⏳ Thinking...")
    
    async def _handle_agent_complete(self, event: AgentCompleteEvent) -> None:
        """Handle completion - show final response with all accumulated content."""
        if event.session_id not in self.message_stack:
            return
            
        # Get accumulated text and add completion marker
        final_text = self.current_text.get(event.session_id, "")
        if final_text:
            final_text += "\n\n✅ Processing complete!"
        else:
            final_text = "✅ Processing complete!"
        
        # Add total token usage if available
        if event.total_token_usage:
            final_text += f"\n\n{self._format_token_usage(event.total_token_usage)}"
            
        # Update with final message
        await self._update_message(event.session_id, final_text)
        
        # Clean up
        del self.message_stack[event.session_id]
        if event.session_id in self.current_text:
            del self.current_text[event.session_id]
    
    async def _handle_agent_cancelled(self, event: AgentCancelledEvent) -> None:
        """Handle cancellation - show cancellation message and clean up."""
        if event.session_id not in self.message_stack:
            return
            
        # Get accumulated text and add cancellation marker
        final_text = self.current_text.get(event.session_id, "")
        if final_text:
            final_text += f"\n\n🛑 Processing cancelled: {event.reason}"
        else:
            final_text = f"🛑 Processing cancelled: {event.reason}"
            
        # Update with final message
        await self._update_message(event.session_id, final_text)
        
        # Clean up
        del self.message_stack[event.session_id]
        if event.session_id in self.current_text:
            del self.current_text[event.session_id]
    
    async def _handle_error(self, event: ErrorEvent) -> None:
        """Handle error event - send new message without deleting previous one."""
        error_text = f"❌ Error: {event.error}"
        
        # Always send error as a new message to preserve previous steps
        await self.bot.send_message(
            self.chat_id,
            error_text,
            parse_mode='HTML'
        )
        
        # Clean up session tracking
        if event.session_id in self.message_stack:
            del self.message_stack[event.session_id]
        if event.session_id in self.current_text:
            del self.current_text[event.session_id]
    
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
                parse_mode='HTML'
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
            parts.append(f"Path: <code>{self._escape_html(parameters['path'])}</code>")
        elif "json_path" in parameters:
            parts.append(f"Path: <code>{self._escape_html(parameters['json_path'])}</code>")
            
        if "value" in parameters:
            value = parameters["value"]
            if isinstance(value, (dict, list)):
                parts.append("Value: [complex object]")
            else:
                parts.append(f"Value: <code>{self._escape_html(str(value))}</code>")
                
        if "old_string" in parameters and "new_string" in parameters:
            parts.append(f"Replace: <code>{self._escape_html(parameters['old_string'][:20])}...</code>")
            
        return " | ".join(parts[:2])  # Limit to 2 items for brevity
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters for Telegram HTML parse mode."""
        return (str(text)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
    
    def _format_token_usage(self, token_usage: TokenUsage) -> str:
        """Format token usage for display."""
        return f"📊 <i>Tokens: {token_usage.input_tokens}→{token_usage.output_tokens} ({token_usage.total_tokens})</i>"