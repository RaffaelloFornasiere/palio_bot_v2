"""Anthropic client implementation."""

import os
import json
from typing import Any, Dict, List, Optional
from anthropic import AsyncAnthropic

from .base_client import BaseLLMClient
from palio_bot.agent.models import Message, TextContent, ToolUseContent, ToolResultContent, Tool, TokenUsage
from palio_bot.utils.api_logger import APILogger


class AnthropicClient(BaseLLMClient):
    """Anthropic client for Claude API."""
    
    def __init__(self, api_key: Optional[str] = None, log_dir: str = "logs", 
                 model: str = "claude-3-5-sonnet-20241022", timeout: float = 300.0,
                 temperature: float = 0.7, max_tokens: int = 4096):
        """Initialize Anthropic client.
        
        Args:
            api_key: Anthropic API key. If not provided, will use ANTHROPIC_API_KEY env var.
            log_dir: Directory for API logs (default: "logs")
            model: Model name to use (default: "claude-3-5-sonnet-20241022")
            timeout: Request timeout in seconds (default: 300.0)
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Maximum tokens to generate (default: 4096)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")
        
        # Store configuration parameters
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        self.client = AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
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
        # Convert messages to Anthropic format with caching
        anthropic_messages = self._convert_messages_to_anthropic(messages, add_cache_to_last=True)
        
        # Add context as a separate cached message if provided
        if context:
            context_text = "<context>\n" + "\n\n".join([c.text for c in context]) + "\n</context>"
            context_message = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": context_text,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            }
            # Insert context message at the beginning (after any existing context)
            anthropic_messages.insert(0, context_message)
        
        # Prepare kwargs for create method
        create_kwargs = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        # Add system prompt with caching if provided
        if system_prompt:
            create_kwargs["system"] = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        
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
    
    def _convert_messages_to_anthropic(self, messages: List[Message], add_cache_to_last: bool = False) -> List[Dict[str, Any]]:
        """Convert our Message format to Anthropic message format."""
        anthropic_messages = []
        
        for i, msg in enumerate(messages):
            is_last_message = (i == len(messages) - 1)
            
            # Convert role
            role = msg.role
            
            # Convert content
            content = []
            for content_item in msg.content:
                if isinstance(content_item, TextContent):
                    text_block = {
                        "type": "text",
                        "text": content_item.text
                    }
                    # Add cache control if present on the content item
                    if content_item.cache_control:
                        text_block["cache_control"] = {"type": content_item.cache_control.type}
                    # Or if this is the last message and we want to cache it
                    elif add_cache_to_last and is_last_message:
                        text_block["cache_control"] = {"type": "ephemeral"}
                    content.append(text_block)
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
                        if content_item.tool_result.data:
                            result_content.append({
                                "type": "text",
                                "text": json.dumps(content_item.tool_result.data, indent=2)
                            })
                        else:
                            result_content.append({
                                "type": "text",
                                "text": "Tool executed successfully, no data returned."
                            })
                    else:
                        # Use error field for error messages when success=False
                        error_msg = f"Tool error: {content_item.tool_result.error or 'Unknown error'}"
                        if content_item.tool_result.data:
                            error_msg += f"\n{json.dumps(content_item.tool_result.data)}"
                        result_content.append({
                            "type": "text",
                            "text": error_msg
                        })
                    
                    content.append({
                        "type": "tool_result",
                        "tool_use_id": content_item.tool_use_id,
                        "content": result_content
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
        
        # Extract token usage from Anthropic response
        token_usage = None
        if hasattr(response, 'usage') and response.usage:
            usage = response.usage
            input_tokens = getattr(usage, 'input_tokens', 0)
            output_tokens = getattr(usage, 'output_tokens', 0)
            total_tokens = input_tokens + output_tokens
            
            token_usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens
            )
        
        return Message(
            role="assistant",
            content=content_list,
            token_usage=token_usage
        )