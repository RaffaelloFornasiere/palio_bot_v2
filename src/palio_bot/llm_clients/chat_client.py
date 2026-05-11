"""OpenAI-compatible chat-completions client.

Works against any server that speaks the `/v1/chat/completions` protocol:
llama.cpp, Ollama's OpenAI shim, OpenRouter, etc.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {429, 502, 503, 504}
_MAX_RETRIES = 4
_BASE_BACKOFF_S = 1.5

from .base_client import BaseLLMClient
from palio_bot.agent.models import Message, TextContent, ToolUseContent, ToolResultContent, Tool, TokenUsage
from palio_bot.utils.api_logger import APILogger


class ChatClient(BaseLLMClient):
    """OpenAI-compatible chat-completions client.

    Works against any server that speaks the `/v1/chat/completions` protocol:
    llama.cpp, Ollama's OpenAI shim, OpenRouter, etc.
    """

    def __init__(
        self,
        base_url: str = "http://mac-studio.local:11454",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        provider_label: str = "llamacpp",
        log_dir: str = "logs",
    ):
        # Accept both "https://host/api" and "https://host/api/v1" — we append /v1
        # ourselves, so strip a trailing /v1 if the caller already included it.
        base = base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        self.base_url = base
        self.chat_endpoint = f"{self.base_url}/v1/chat/completions"
        self.api_key = api_key
        self.model = model
        self.extra_headers = extra_headers or {}
        self.provider_label = provider_label
        self.api_logger = APILogger(log_dir=log_dir)

    async def generate_message(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        context: Optional[List["TextContent"]] = None,
        tools: Optional[List[Tool]] = None
    ) -> Message:
        """Generate a response message via the OpenAI-compatible endpoint."""
        openai_messages = self._convert_messages_to_openai(messages, system_prompt, context)

        payload: Dict[str, Any] = {
            "messages": openai_messages,
            "temperature": 0.7,
            "max_tokens": 16384,
            "stream": False,
        }
        if self.model:
            payload["model"] = self.model
        if tools:
            payload["tools"] = self._convert_tools_to_openai(tools)
        if self.provider_label == "llamacpp":
            payload["cache_prompt"] = True  # llama.cpp-specific; harmless on others but keep it scoped

        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request_filepath = self.api_logger.log_request(payload, provider=self.provider_label)

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await self._post_with_retry(client, payload, headers)

                if response.status_code != 200:
                    raise Exception(
                        f"{self.provider_label} API error {response.status_code}: {response.text}"
                    )

                result = response.json()
                self.api_logger.log_response(result, request_filepath, provider=self.provider_label)
                return self._convert_response_to_message(result)

        except Exception as e:
            self.api_logger.log_error(e, request_filepath, provider=self.provider_label)
            raise e

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> httpx.Response:
        """POST with exponential backoff on rate-limits and transient 5xx."""
        last_response: Optional[httpx.Response] = None
        for attempt in range(_MAX_RETRIES + 1):
            response = await client.post(self.chat_endpoint, json=payload, headers=headers)
            last_response = response

            if response.status_code not in _RETRYABLE_STATUSES:
                return response
            if attempt == _MAX_RETRIES:
                return response

            # Honor Retry-After if present, else exponential backoff.
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    sleep_s = float(retry_after)
                except ValueError:
                    sleep_s = _BASE_BACKOFF_S * (2 ** attempt)
            else:
                sleep_s = _BASE_BACKOFF_S * (2 ** attempt)

            logger.warning(
                f"{self.provider_label} returned {response.status_code}; "
                f"retrying in {sleep_s:.1f}s (attempt {attempt + 1}/{_MAX_RETRIES})"
            )
            await asyncio.sleep(sleep_s)

        # Unreachable given the returns above, but keep mypy happy.
        assert last_response is not None
        return last_response
    
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
            openai_messages.append(
                {
                    "role": "system",
                    "content": system_prompt
                },
            )
        if context:
            # Add context content if provided
            if context:
                context_text = "<context>\n"
                context_text += "\n\n".join([c.text for c in context])
                context_text += "\n</context>"

                openai_messages.append(
                    {
                        "role": "user",
                        "content": context_text
                    }
                )

        
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
            
            # Handle regular messages: may carry text, tool_calls, or both.
            openai_msg: Dict[str, Any] = {"role": msg.role}
            text_parts: List[str] = []
            tool_calls: List[Dict[str, Any]] = []

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
                            "arguments": json.dumps(content.tool_parameters),
                        },
                    })

            # Always include tool_calls if present, even alongside text.
            # OpenAI (and providers like Bedrock-via-OpenRouter) require the
            # assistant's tool_calls to be in the same message as any
            # preceding text, otherwise a later tool_result is orphaned.
            if tool_calls:
                openai_msg["tool_calls"] = tool_calls
                openai_msg["content"] = "\n".join(text_parts) if text_parts else None
            else:
                openai_msg["content"] = "\n".join(text_parts) if text_parts else ""

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
        # Providers (OpenRouter etc.) sometimes return 200 with an error
        # envelope instead of `choices`. Surface a useful error instead of
        # crashing with a bare `KeyError: 'choices'`.
        choices = response.get("choices")
        if not choices:
            err = response.get("error")
            if isinstance(err, dict):
                msg = err.get("message") or json.dumps(err, ensure_ascii=False)
                code = err.get("code")
                detail = f"{self.provider_label} error" + (f" [{code}]" if code else "") + f": {msg}"
            else:
                detail = (
                    f"{self.provider_label} returned no choices: "
                    f"{json.dumps(response, ensure_ascii=False)[:500]}"
                )
            raise RuntimeError(detail)
        choice = choices[0]
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
        
        # Extract token usage from response
        token_usage = None
        if "usage" in response:
            usage = response["usage"]
            token_usage = TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0)
            )
        
        return Message(
            role="assistant",
            content=content_list,
            token_usage=token_usage
        )