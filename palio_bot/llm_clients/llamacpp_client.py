"""LlamaCPP client implementation."""

import json
from typing import Any, Dict, List, Optional
import httpx

from .base_client import BaseLLMClient
from palio_bot.agent.models import Message, TextContent, ToolUseContent, ToolResultContent, Tool
from palio_bot.utils.api_logger import APILogger


class LlamaCPPClient(BaseLLMClient):
    """LlamaCPP client for local model inference."""
    
    def __init__(self, base_url: str = "http://mac-studio.local:11454", log_dir: str = "logs"):
        self.base_url = base_url.rstrip("/")
        self.chat_endpoint = f"{self.base_url}/v1/chat/completions"
        self.api_logger = APILogger(log_dir=log_dir)
    
    async def generate_message(
        self, 
        messages: List[Message], 
        system_prompt: Optional[str] = None,
        context: Optional[List["TextContent"]] = None,
        tools: Optional[List[Tool]] = None
    ) -> Message:
        """Generate a response message from LlamaCPP.
        
        Args:
            messages: List of messages in the conversation
            system_prompt: Optional system prompt string
            context: Optional list of TextContent for additional context
            tools: Optional list of Tool objects
            
        Returns:
            Message containing the LLM response
        """
        # Convert our messages to OpenAI format
        openai_messages = self._convert_messages_to_openai(messages, system_prompt, context)
        
        # Prepare request payload
        payload = {
            "messages": openai_messages,
            "temperature": 0.7,
            "max_tokens": 16384,
            "stream": False
        }
        
        # Add tools if provided
        if tools:
            payload["tools"] = self._convert_tools_to_openai(tools)
            payload["tool_choice"] = "auto"

        payload["cache_prompt"] = True  # Enable caching for LlamaCPP
        # Log the request
        request_filepath = self.api_logger.log_request(payload, provider="llamacpp")
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    self.chat_endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    raise Exception(f"LlamaCPP API error {response.status_code}: {error_text}")
                
                result = response.json()


                # Log the response
                self.api_logger.log_response(result, request_filepath, provider="llamacpp")
                
                return self._convert_response_to_message(result)
                
        except Exception as e:
            # Log the error
            self.api_logger.log_error(e, request_filepath, provider="llamacpp")
            raise e
    
    def _convert_messages_to_openai(
        self, 
        messages: List[Message], 
        system_prompt: Optional[str] = None,
        context: Optional[List[TextContent]] = None
    ) -> List[Dict[str, Any]]:
        """Convert our Message format to OpenAI chat format."""
        openai_messages = []
        
        # Add system message if system_prompt provided
        if system_prompt:
            system_content = ""
            # Add context content if provided
            if context:
                context_text = "\n\n".join([c.text for c in context])
                system_content += f"\n\n{context_text}"

            # Add system prompt
            system_content += f"\n\n{system_prompt}"
            
            openai_messages.append({
                "role": "system",
                "content": system_content
            })
        
        # Convert each message
        for msg in messages:
            # Check if this is a tool result message (should be alone)
            if len(msg.content) == 1 and isinstance(msg.content[0], ToolResultContent):
                content = msg.content[0]
                
                # Format tool result content
                if content.tool_result.success:
                    tool_content = json.dumps(content.tool_result.data, indent=2) if content.tool_result.data else "Tool executed successfully, no data returned."
                else:
                    error_msg = f"Tool error: {content.tool_result.error or 'Unknown error'}"
                    if content.tool_result.data:
                        error_msg += f"\n{json.dumps(content.tool_result.data, indent=2)}"
                    tool_content = error_msg
                
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": content.tool_use_id,
                    "content": tool_content
                })
                continue
            
            # Handle regular messages
            openai_msg = {"role": msg.role}
            
            # Single text content
            if len(msg.content) == 1 and isinstance(msg.content[0], TextContent):
                openai_msg["content"] = msg.content[0].text
            else:
                # Mixed content or tool calls
                text_parts = []
                tool_calls = []
                
                for content in msg.content:
                    if isinstance(content, TextContent):
                        if content.text.strip():
                            text_parts.append(content.text)
                    elif isinstance(content, ToolUseContent):
                        tool_calls.append({
                            "id": content.tool_use_id,
                            "type": "function",
                            "function": {
                                "name": content.tool_name,
                                "arguments": json.dumps(content.tool_parameters)
                            }
                        })
                
                if text_parts:
                    openai_msg["content"] = "\n".join(text_parts)
                elif tool_calls:
                    openai_msg["tool_calls"] = tool_calls
                    # OpenAI expects content to be null for tool calls
                else:
                    openai_msg["content"] = ""
            
            openai_messages.append(openai_msg)
        
        return openai_messages
    
    def _convert_tools_to_openai(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Convert Tool objects to OpenAI tools format."""
        openai_tools = []
        
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema
                }
            })
        
        return openai_tools
    
    def _convert_response_to_message(self, response: Dict[str, Any]) -> Message:
        """Convert OpenAI response to our Message format."""
        choice = response["choices"][0]
        message = choice["message"]
        
        content_list = []
        
        # Handle text content
        if message.get("content"):
            # fix https://github.com/ggml-org/llama.cpp/issues/14697
            try:
                content_json = json.loads(message["content"])
                if "tool_calls" in content_json:
                    # If content is a JSON object with tool calls
                    message["tool_calls"] = content_json.get("tool_calls", [])
            except json.decoder.JSONDecodeError:
                content_list.append(TextContent(text=message["content"]))
        
        # Handle tool calls
        if message.get("tool_calls"):
            for tool_call in message["tool_calls"]:
                function = tool_call["function"]
                content_list.append(ToolUseContent(
                    tool_name=function["name"],
                    tool_parameters=json.loads(function["arguments"]),
                    tool_use_id=tool_call["id"]
                ))
        
        # If no content, add empty text
        if not content_list:
            content_list.append(TextContent(text=""))
        
        return Message(
            role="assistant",
            content=content_list
        )