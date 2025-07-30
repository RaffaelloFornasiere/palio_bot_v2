"""Ollama client implementation."""

import json
from typing import Any, Dict, List, Optional
import asyncio
import ollama

from .base_client import BaseLLMClient
from palio_bot.agent.models import Message, TextContent, ToolUseContent, ToolResultContent, Tool, TokenUsage
from palio_bot.utils.api_logger import APILogger


class OllamaClient(BaseLLMClient):
    """Ollama client for local model inference."""
    
    def __init__(self, base_url: str = "http://mac-studio.local:11434", model: str = "llama3.2", log_dir: str = "logs", 
                 num_gpu: int = -1, num_batch: int = 512, num_thread: int = 8):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_gpu = num_gpu
        self.num_batch = num_batch
        self.num_thread = num_thread
        self.api_logger = APILogger(log_dir=log_dir)
        # Initialize ollama client with custom host and longer timeout (5 minutes)
        self.client = ollama.Client(host=self.base_url, timeout=300.0)
    
    async def generate_message(
        self, 
        messages: List[Message], 
        system_prompt: Optional[str] = None,
        context: Optional[List["TextContent"]] = None,
        tools: Optional[List[Tool]] = None
    ) -> Message:
        """Generate a response message from Ollama.
        
        Args:
            messages: List of messages in the conversation
            system_prompt: Optional system prompt string
            context: Optional list of TextContent for additional context
            tools: Optional list of Tool objects
            
        Returns:
            Message containing the LLM response
        """
        # Convert our messages to Ollama format
        ollama_messages = self._convert_messages_to_ollama(messages, system_prompt, context)
        
        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "options": {
                "temperature": 0.7,
                "num_ctx": 16384,  # Always use 16k context
                "num_gpu": -1,  # Always use full GPU
            },
            "stream": False,
        }
        
        # Add tools if provided
        if tools:
            payload["tools"] = self._convert_tools_to_ollama(tools)

        # Log the request
        request_filepath = self.api_logger.log_request(payload, provider="ollama")
        
        try:
            # Run the synchronous ollama.chat in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat(**payload)
            )
            
            # Log the response
            self.api_logger.log_response(response, request_filepath, provider="ollama")
            

            return self._convert_response_to_message(response)
                
        except Exception as e:
            # Log the error
            self.api_logger.log_error(e, request_filepath, provider="ollama")
            raise e
    
    def _convert_messages_to_ollama(
        self, 
        messages: List[Message], 
        system_prompt: Optional[str] = None,
        context: Optional[List[TextContent]] = None
    ) -> List[Dict[str, Any]]:
        """Convert our Message format to Ollama chat format."""
        ollama_messages = []
        
        # Add system message if system_prompt provided
        if system_prompt:
            ollama_messages.append({
                "role": "system",
                "content": system_prompt
            })
            
        if context:
            # Add context content if provided
            context_text = "<context>\n"
            context_text += "\n\n".join([c.text for c in context])
            context_text += "\n</context>"

            ollama_messages.append({
                "role": "user",
                "content": context_text
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
                
                ollama_messages.append({
                    "role": "tool",
                    "content": tool_content
                })
                continue
            
            # Handle regular messages
            ollama_msg = {"role": msg.role}
            
            # Single text content
            if len(msg.content) == 1 and isinstance(msg.content[0], TextContent):
                ollama_msg["content"] = msg.content[0].text
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
                            "function": {
                                "name": content.tool_name,
                                "arguments": content.tool_parameters
                            }
                        })
                
                if text_parts:
                    ollama_msg["content"] = "\n".join(text_parts)
                
                if tool_calls:
                    ollama_msg["tool_calls"] = tool_calls
                    
                if not text_parts and not tool_calls:
                    ollama_msg["content"] = ""
            
            ollama_messages.append(ollama_msg)
        
        return ollama_messages
    
    def _convert_tools_to_ollama(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Convert Tool objects to Ollama tools format."""
        ollama_tools = []
        
        for tool in tools:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema
                }
            })
        
        return ollama_tools
    
    def _convert_response_to_message(self, response: Dict[str, Any]) -> Message:
        """Convert Ollama response to our Message format."""
        message = response.get("message", {})
        
        content_list = []
        
        # Handle text content
        if message.get("content"):
            content_list.append(TextContent(text=message["content"]))
        
        # Handle tool calls
        if message.get("tool_calls"):
            for tool_call in message["tool_calls"]:
                function = tool_call.get("function", {})
                # Generate a unique ID for the tool use
                import uuid
                tool_use_id = f"tool_{uuid.uuid4().hex[:8]}"
                
                content_list.append(ToolUseContent(
                    tool_name=function.get("name", ""),
                    tool_parameters=function.get("arguments", {}),
                    tool_use_id=tool_use_id
                ))
        
        # If no content, add empty text
        if not content_list:
            content_list.append(TextContent(text=""))
        
        # Extract token usage and timing from Ollama response format
        token_usage = None
        if "prompt_eval_count" in response or "eval_count" in response:
            input_tokens = response.get("prompt_eval_count", 0)
            output_tokens = response.get("eval_count", 0)
            total_tokens = input_tokens + output_tokens
            
            # Extract timing information (all in nanoseconds)
            prompt_eval_duration_ns = response.get("prompt_eval_duration")
            eval_duration_ns = response.get("eval_duration")
            total_duration_ns = response.get("total_duration")
            
            token_usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                prompt_eval_duration_ns=prompt_eval_duration_ns,
                eval_duration_ns=eval_duration_ns,
                total_duration_ns=total_duration_ns
            )
        
        return Message(
            role="assistant",
            content=content_list,
            token_usage=token_usage
        )