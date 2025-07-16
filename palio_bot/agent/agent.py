"""Agent implementation as async generator for processing messages."""

import logging
from typing import Dict, List, Optional, AsyncGenerator

from palio_bot.agent.models import (
    Message, TextContent, ToolUseContent, Tool, ToolResult, AgentContextBlock,
)
from palio_bot.agent.system_prompt import _get_system_prompt
from palio_bot.llm_clients.base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class Agent:
    """Agent that processes messages as async generator."""
    
    def __init__(
        self, 
        llm_client: BaseLLMClient, 
        tools: Dict[str, Tool]
    ):
        self.llm_client = llm_client
        self.tools = tools  # Dict[tool_name, Tool]
        self.system_prompt = _get_system_prompt()
        logger.info(f"Agent initialized with {len(tools)} tools: {list(tools.keys())}")
    
    async def run(
        self, 
        messages: List[Message],
        context: Optional[List[AgentContextBlock]] = None
    ) -> AsyncGenerator[Message, None]:
        """Process messages as async generator yielding responses.
        
        Args:
            messages: Complete conversation history
            context: Optional context (e.g., current palio.json content)
            
        Yields:
            AgentResponse objects (LLMResponse, ToolUseResponse, ToolResultResponse)
        """
        logger.info(f"\n{'='*60}\nAgent.run() called\nMessages: {len(messages)}\n{'='*60}")
        
        # Format context
        formatted_context = [ctx.format() for ctx in context] if context else []
        
        # Process through tool loop
        logger.info("Starting agent processing loop")
        current_messages = messages.copy()
        
        # Continue loop until LLM responds with text only (no tool calls)
        iteration = 0
        while True:
            iteration += 1
            logger.info(f"\n--- Agent loop iteration {iteration} ---")
            
            # Get response from LLM
            logger.info(f"Calling LLM with {len(current_messages)} messages")
            response_message = await self.llm_client.generate_message(
                messages=current_messages,
                system_prompt=self.system_prompt,
                context=formatted_context,
                tools=list(self.tools.values())
            )
            logger.info(f"LLM response received: role={response_message.role}, content_types={[c.type for c in response_message.content]}")
            
            # Yield LLM response
            yield response_message
            
            # Add LLM response to current conversation
            current_messages.append(response_message)
            
            # Check if response contains tool calls
            tool_uses = [
                content for content in response_message.content
                if isinstance(content, ToolUseContent)
            ]
            
            if not tool_uses:
                # LLM responded with text only, end the loop
                logger.info("No tool uses in response. Ending agent loop.")
                break
            
            logger.info(f"Found {len(tool_uses)} tool uses: {[tu.tool_name for tu in tool_uses]}")
            
            # Process tool uses
            for tool_use in tool_uses:
                # Execute tool
                logger.info(f"  Executing tool: {tool_use.tool_name}")
                logger.debug(f"  Parameters: {tool_use.tool_parameters}")
                tool_result = await self._execute_tool(tool_use)
                logger.info(f"  Tool result: success={tool_result.success}")

                
                # Create tool result message and add to conversation
                result_message = Message.tool_result(
                    role="user",
                    tool_result=tool_result,
                    tool_use_id=tool_use.tool_use_id
                )

                current_messages.append(result_message)

                yield result_message

        logger.info("Agent.run() completed successfully")
    
    
    async def _execute_tool(self, tool_use: ToolUseContent) -> ToolResult:
        """Execute a tool and return the result.
        
        Args:
            tool_use: ToolUseContent with tool name and parameters
            
        Returns:
            ToolResult (always returns a structured result, never raises)
        """
        tool_name = tool_use.tool_name
        
        if tool_name not in self.tools:
            logger.error(f"Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}")
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
                data={"available_tools": list(self.tools.keys())}
            )
        
        try:
            tool = self.tools[tool_name]
            logger.debug(f"Calling tool function with parameters: {tool_use.tool_parameters}")
            result = tool.call(**tool_use.tool_parameters)
            logger.debug(f"Tool returned: {result}")
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                data={
                    "tool_name": tool_name,
                    "parameters": tool_use.tool_parameters
                }
            )
    
