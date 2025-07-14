"""Base LLM client interface."""

from abc import ABC, abstractmethod
from typing import List, Optional

from palio_bot.agent.models import Message, Tool, TextContent


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    @abstractmethod
    async def generate_message(
        self, 
        messages: List[Message], 
        system_prompt: Optional[str] = None,
        context: Optional[List[TextContent]] = None,
        tools: Optional[List[Tool]] = None
    ) -> Message:
        """Generate a response message from the LLM.
        
        Args:
            messages: List of messages in the conversation
            system_prompt: Optional system prompt string
            context: Optional list of TextContent for additional context
            tools: Optional list of Tool objects
            
        Returns:
            Message containing the LLM response (TextContent or ToolUseContent)
        """
        pass