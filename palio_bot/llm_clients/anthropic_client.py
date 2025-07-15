"""Anthropic client implementation."""

import os
import json
from typing import Any, Dict, List, Optional
from anthropic import AsyncAnthropic

from .base_client import BaseLLMClient
from palio_bot.agent.models import Message, TextContent, ToolUseContent, ToolResultContent, Tool
from palio_bot.utils.api_logger import APILogger


class AnthropicClient(BaseLLMClient):
    """Anthropic client for Claude API."""
    
    def __init__(self, api_key: Optional[str] = None, log_dir: str = "logs"):
        """Initialize Anthropic client.
        
        Args:
            api_key: Anthropic API key. If not provided, will use ANTHROPIC_API_KEY env var.
            log_dir: Directory for API logs (default: "logs")
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")
        
        self.client = AsyncAnthropic(api_key=self.api_key)
        self.api_logger = APILogger(log_dir=log_dir)
    
    async def generate_message(
        self, 
        messages: List[Message], 
        system_prompt: Optional[str] = None,
        context: Optional[List["TextContent"]] = None,
        tools: Optional[List[Tool]] = None
    ) -> Message:
        """Generate a response message from Anthropic Claude.
        
        Args:
            messages: List of messages in the conversation
            system_prompt: Optional system prompt string
            context: Optional list of TextContent for additional context
            tools: Optional list of Tool objects
            
        Returns:
            Message containing the Claude response
        """
        # Prepare system prompt with context if provided
        full_system_prompt = system_prompt or ""
        if context:
            context_text = "\n\n".join([c.text for c in context])
            full_system_prompt = f"{full_system_prompt}\n\n{context_text}" if full_system_prompt else context_text
        
        # Convert messages to Anthropic format
        anthropic_messages = self._convert_messages_to_anthropic(messages)
        
        # Prepare kwargs for create method
        create_kwargs = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": anthropic_messages,
            "max_tokens": 4096,
            "temperature": 0.7
        }
        
        # Add system prompt if provided
        if full_system_prompt:
            create_kwargs["system"] = full_system_prompt
        
        # Add tools if provided
        if tools:
            create_kwargs["tools"] = self._convert_tools_to_anthropic(tools)
        
        # Log the request
        request_filepath = self.api_logger.log_request(create_kwargs, provider="anthropic")
        
        try:
            # Make API call
            response = await self.client.messages.create(**create_kwargs)
            
            # Log the response
            self.api_logger.log_response(response, request_filepath, provider="anthropic")
            
        except Exception as e:
            # Log the error
            self.api_logger.log_error(e, request_filepath, provider="anthropic")
            raise e
        
        # Convert response to our Message format
        return self._convert_response_to_message(response)
    
    def _convert_messages_to_anthropic(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert our Message format to Anthropic message format."""
        anthropic_messages = []
        
        for msg in messages:
            if msg.role == "event":
                continue  # Skip event messages
            
            # Convert role
            role = msg.role
            if role == "human":
                role = "user"
            
            # Convert content
            content = []
            for content_item in msg.content:
                if isinstance(content_item, TextContent):
                    content.append({
                        "type": "text",
                        "text": content_item.text
                    })
                elif isinstance(content_item, ToolUseContent):
                    content.append({
                        "type": "tool_use",
                        "id": content_item.tool_use_id,
                        "name": content_item.tool_name,
                        "input": content_item.tool_parameters
                    })
                elif isinstance(content_item, ToolResultContent):
                    result_content = []
                    if content_item.tool_result.success:
                        if content_item.tool_result.message:
                            result_content.append({
                                "type": "text",
                                "text": content_item.tool_result.message
                            })
                        if content_item.tool_result.data:
                            result_content.append({
                                "type": "text",
                                "text": json.dumps(content_item.tool_result.data, indent=2)
                            })
                    else:
                        # Use error field for error messages when success=False
                        error_msg = f"Tool error: {content_item.tool_result.error or content_item.tool_result.message or 'Unknown error'}"
                        if content_item.tool_result.data:
                            error_msg += f"\n{json.dumps(content_item.tool_result.data)}"
                        result_content.append({
                            "type": "text",
                            "text": error_msg
                        })
                    
                    content.append({
                        "type": "tool_result",
                        "tool_use_id": content_item.tool_use_id,
                        "content": result_content if result_content else [{"type": "text", "text": "Success"}]
                    })
            
            # Only add message if it has content
            if content:
                anthropic_messages.append({
                    "role": role,
                    "content": content
                })
        
        return anthropic_messages
    
    def _convert_tools_to_anthropic(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Convert Tool objects to Anthropic tools format."""
        anthropic_tools = []
        
        for tool in tools:
            anthropic_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters_schema
            })
        
        return anthropic_tools
    
    def _convert_response_to_message(self, response) -> Message:
        """Convert Anthropic response to our Message format."""
        content_list = []
        
        # Convert each content block
        for content_block in response.content:
            if content_block.type == "text":
                content_list.append(TextContent(text=content_block.text))
            elif content_block.type == "tool_use":
                content_list.append(ToolUseContent(
                    tool_name=content_block.name,
                    tool_parameters=content_block.input,
                    tool_use_id=content_block.id
                ))
        
        return Message(
            role="assistant",
            content=content_list
        )